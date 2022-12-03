#-----------------------------
# -- Angola --
#-----------------------------

import copy 
from typing import Any, List
from arango import ArangoClient
from contextlib import contextmanager
from . import lib, lib_xql, dict_mutator, dict_query


DEFAULT_INDEXES = [
    {
        "type": "persistent",
        "fields": ["_created_at"],
        "name": "idx_created_at__0"
    },
    {
        "type": "persistent",
        "fields": ["_modified_at"],
        "name": "idx_modified_at__0"
    },
    {
        "type": "ttl",
        "fields": ["__ttl"],
        "name": "idx_ttl__0",
        "expireAfter": 0
    }
]

#------------------------------------------------------------------------------
# Exception
class AngolaError(Exception): pass
class AdapterError(AngolaError): pass
class CollectionNotFoundError(AngolaError): pass
class CollectionExistsError(AngolaError): pass
class ItemNotFoundError(AngolaError):pass
class ItemExistsError(AngolaError):pass
class NoResultsError(AngolaError): pass
class ConstraintError(AngolaError): pass
class UndeletableError(AngolaError): pass
class MissingCommitterCallbackError(AngolaError): pass
class MissingItemKeyError(AngolaError): pass
class InvalidItemPathError(AngolaError): pass 

#------------------------------------------------------------------------------

class QueryResult(object):
    def __init__(self, cursor, pager, data_mapper=None):
        self.cursor = cursor
        stats = cursor.statistics()
        self.count = self.cursor.count()
        self.total_count = stats["fullCount"]
        self.pagination = lib.gen_pagination(total_count=self.total_count,
                                            count=self.count,
                                            page=pager[0],
                                            per_page=pager[1])

        def _default_data_mapper_cb(item): return item 
    
        self._data_mapper = _default_data_mapper_cb if not data_mapper else data_mapper

    def __iter__(self):
        for item in self.cursor:
            yield self._data_mapper(item)

    def __len__(self):
        return self.total_count

class Item_Impl(dict):
    NAMESPACE = None
 
    def _make_path(self, path):
        # if self.NAMESPACE:
        #     return "%s.%s" % (self.NAMESPACE, path)
        return path

    def _update(self, data):
        raise NotImplementedError()

    def get(self, path: str, default: Any = None) -> Any:
        """
        GET: Return a property by key/DotNotation

        ie: 
            #get("key.deep1.deep2.deep3")

        Params:
            path:str - the dotnotation path
            default:Any - default value 

        Returns:
            Any
        """
        path = self._make_path(path)
        return lib.dict_get(obj=dict(self), path=path, default=default)

    def set(self, path: str, value: Any):
        """
        SET: Set a property by key/DotNotation

        Params:
            path:str - the dotnotation path
            value:Any - The value

        Returns:
            Void
        """

        path = self._make_path(path)
        self._update({path: value})
        return self

    def len(self, path: str):
        """
        Get the length of the items in a str/list/dict
        Params:
            path:str - the dotnotation path
        Returns:
            data that was removed
        """
        path = self._make_path(path)
        v = self.get(path)
        return len(v) if v else 0

    def incr(self, path: str, incr=1):
        """
        INCR: increment a value by 1
        Args
            path:str - path
            incr:1 - value to inc by
        Returns:    
            int - the value that was incremented
        """
        op = "%s:$incr" % self._make_path(path)        
        oplog = self._update({op: incr})
        return oplog.get(op)

    def decr(self, path: str, decr=1):
        """
        DECR: decrement a value by 1
        Args
            path:str - path
            decr:1 - value to dec by
        Returns:    
            int - the value that was decremented
        """
        op = "%s:$decr" % self._make_path(path)

        oplog = self._update({op: decr})
        return oplog.get(op)

    def unset(self, path: str):
        """ 
        UNSET: Remove a property by key/DotNotation and return the value

        Params:
            path:str

        Returns:
            Any: the value that was removed
        """
        path = self._make_path(path)
        self._update({"%s:$unset" % path: True})

    def xadd(self, path: str, values):
        """
        LADD: Add *values if they don't exist yet

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xadd" % self._make_path(path)
        self._update({op: values})

    def xadd_many(self, path: str, *values: List[Any]):
        """
        LADD: Add *values if they don't exist yet

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xadd_many" % self._make_path(path)
        self._update({op: values})

    def xrem(self, path: str, values):
        """
        LREM: Remove items from a list

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xrem" % self._make_path(path)
        oplog = self._update({op: values})
        return oplog.get(op)

    def xrem_many(self, path: str, *values: List[Any]):
        """
        LREM: Remove items from a list

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xrem_many" % self._make_path(path)
        oplog = self._update({op: values})
        return oplog.get(op)

    def xpush(self, path: str, values: Any):
        """
        LPUSH: push item to the right of list. 

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xpush" % self._make_path(path)
        self._update({op: values})

    def xpush_many(self, path: str, *values: List[Any]):
        """
        LPUSH: push item to the right of list. 

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xpush_many" % self._make_path(path)
        self._update({op: values})

    def xpushl(self, path: str, values: Any):
        """
        LPUSH: push item to the right of list. 

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xpushl" % self._make_path(path)
        self._update({op: values})

    def xpushl_many(self, path: str, *values: List[Any]):
        """
        LPUSH: push item to the right of list. 

        Params:
            path:str - the dotnotation path
            *values: set of items
        Returns:
            list: updated data
        """
        op = "%s:$xpush_many" % self._make_path(path)
        self._update({op: values})

    def xpop(self, path: str):
        """
        Remove value at the end an array/list
        Params:
            path:str - the dotnotation path
        Returns:
            data that was removed

        """
        op = "%s:$xpop" % self._make_path(path)
        oplog = self._update({op: True})
        return oplog.get(op)

    def xpopl(self, path: str):
        """
        Remove value at the beginning an array/list
        Params:
            path:str - the dotnotation path
        Returns:
            data that was removed        
        """
        op = "%s:$xpopl" % self._make_path(path)
        oplog = self._update({op: True})
        return oplog.get(op)

    def currdate(self, path:str, value:Any=True):
        op = "%s:$currdate" % self._make_path(path)
        oplog = self._update({op: value})
        return oplog.get(op)   

    def template(self, path:str, value:str):
        op = "%s:$template" % self._make_path(path)
        oplog = self._update({op: value})
        return oplog.get(op)

    def uuid4(self, path:str):
        op = "%s:$uuid4" % self._make_path(path)
        oplog = self._update({op: True})
        return oplog.get(op)

    def update(self, data: dict) -> "Self":
        """
        UPDATE: Update the active CollectionItem

        Returns:
            CollectionItem

        Example:
            #item.update({k/v...})
            #item.commit()

            or 
            #item.update({k/v...}).commit()
        """
        self._update(data)
        return self

class CollectionItem(Item_Impl):
    """
    CollectionItem

    Every row is a document 
    """

    # item _key
    _key = None

    # items subcollections
    _subcollections = {}
    
    # immutable keys
    _immut_keys = []

    @classmethod
    def new(cls, data:dict, immut_keys:list=[], commiter=None, custom_ops:dict={}):
      return cls(data=_create_document_item(data), immut_keys=immut_keys, commiter=commiter, custom_ops=custom_ops)

    def __init__(self, data: dict, immut_keys:list=[], load_parser=None, commiter=None, custom_ops:dict={}):
        if "_key" not in data:
            raise MissingItemKeyError()
        
        self._load_parser = load_parser
        self._commiter = commiter
        self._immut_keys = immut_keys
        self._cx = False
        self._custom_ops = custom_ops
    
        data, _ = dict_mutator.mutate(mutations=data,  immuts=immut_keys, custom_ops=self._custom_ops)
        self._load(data)

    def to_dict(self):
        data = dict(self)
        if self._subcollections:
            data["/subcollections"] = self._subcollections
        return data 

    def set_immut_keys(self, immut_keys:list=[]):
        self._immut_keys = immut_keys

    @contextmanager
    def context(self):
        """
        *ContextManager for CollectionItem

        Do transactional mutation and commit the changes upon exit

        Yield:
            CollectionItem

        Example:
            with item.context() as ctx:
                ctx.update({"name": "Y"})

        """
        yield self 
        self.commit()

    @contextmanager
    def context_subcollection(self, name: str, constraints: list = None):
        """
        *Context Manager for Subcollection

        Do transactional mutation on subcollection and commit the changes upon exit

        Yield:
          SubCollection

        Example:

        with item.context_subcollection('name') as sc:
            sc.insert()
        
        """
        sc = SubCollection(item=self, name=name, custom_ops=self._custom_ops)
        yield sc
        self.commit()

    def select_subcollection(self, name: str, constraints: list = None):
        """

        Select a subcollection. When making changes, must use `commit` on parent

        Retuns:
          SubCollection

        Example:
            sc = item.select_subcollection(name)
            sc.insert({...})
            sc.insert({...})
            item.commit()

            -- or with #context
            with item.context() as ictx:
                sc = item.select_subcollection(name)
                sc.insert({...})
                sc.insert({...})
            
            or refer to #context_subscollection

        """
        return SubCollection(item=self, name=name, custom_ops=self._custom_ops)

    def get_item(self, path:str) -> "SubCollectionItem":
        """
        To get a subcollection item via path

        Path: [SUB_COLLECTION_NAME/DOCUMENT_KEY] -> articles/1234568

        Params:
            path:str - str of [sub_collection_name/document_key]
        Return:
            collection.item

        Example:
            db.get_item("collection/_key").get_item("sub_collection/_key")
        
        Returns:
            SubCollectionItem

        """
        
        paths = path.split("/")
        if len(paths) != 2:
            raise InvalidItemPathError()

        return self.select_subcollection(paths[0]).get(paths[1])        

    @property
    def subcollections(self) -> list:
        """ List all collections """
        return list(self._subcollections.keys()) or []

    def drop_subcollection(self, name: str):
        try:
            if name in self._subcollections:
                del self._subcollections[name]
            self.set("/subcollections", self._subcollections)
        except KeyError as _:
            pass
        return True

    def _set_subcollection(self, name:str, data:Any):
        self._subcollections[name] = data
        self.set("/subcollections", self._subcollections)

    def commit(self) -> "Self":
        """ To save """
        if not self._commiter:
            raise MissingCommitterCallbackError()
        data = self._commiter(self)
        if data:
            self._load(data)
        return self
        
    def _update(self, mutations: dict):
        """
        Return oplog
        """
        data = self.to_dict()
        doc, oplog = dict_mutator.mutate(mutations=mutations, init_data=data, immuts=self._immut_keys, custom_ops=self._custom_ops)
        self._load(doc)
        return oplog

    def _load(self, item: dict):
        """
        load the content into the document

        Params:
            row: dict
        """
        self._clear_self()
        
        if self._load_parser:
          item = self._load_parser(item)

        self._subcollections = {}
        if "/subcollections" in item:
            self._subcollections = item.pop("/subcollections") or {}

        if "_key" in item:
            self._key = item.get("_key")
        super().__init__(item)

    def _clear_self(self):
        """ clearout all properties """
        for _ in list(self.keys()):
            if _ in self:
                del self[_]

class SubCollection(object):
    _data = []
    _constraints = []
    _item = None
    _name = None 

    def __init__(self, item: CollectionItem, name: str, constraints:list=None, custom_ops:dict={}):
        self._item = item
        self._name = name
        self._constraints = constraints
        self._load()
        self._custom_ops = custom_ops

    def _load(self):
        self._data = self._item._subcollections.get(self._name) or []

    def _commit(self):
        self._item._set_subcollection(self._name, self._data)

    def _save(self, _key, data):
        _data = self._normalize_data()
        _data[_key] = data
        self._data = self._denormalize_data(_data)
        self._commit()        

    def _normalize_data(self) -> dict:
        return { d.get("_key"): d for d in self._data}

    def _denormalize_data(self, data:dict) -> list:
        return list(data.values())

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self.find())

    @property
    def items(self):
        """ 
        Returns an iterator of all documents

        Returns:
            Iterator
        """
        return self.find()

    def has(self, _key):
        return bool(self.find_one({"_key": _key}))

    def insert(self, data: dict, _key:str=None):
        """
        Insert document

        Params:
            data:dict
            _key: to insert with a _key
        """
        data, _ = dict_mutator.mutate(mutations=data.copy(), immuts=self._item._immut_keys, custom_ops=self._custom_ops)

        if self._constraints:
            for c in  self._constraints:
                if c in data:
                    if self.find_one({c: data[c]}):
                        raise ConstraintError("Key: %s" % c)

        if _key or "_key" in data:
            _key = _key or data["_key"]
            if self.has(_key):
                raise ItemExistsError()
            data["_key"] = _key
        item = data

        item = _create_document_item(data)
        self._data.append(item)
        self._commit()
        return SubCollectionItem(self, item)

    def update(self, filters:dict, mutations: dict, upsert:bool=False):
        """
        Update by filter

        Params:
            filter:dict - filter document criteria
            mutations:dict - changes on the found documents
        """
        _data = self._normalize_data()
        res = self.find(filters)
        if res:
            for item in res:
                ts = lib.get_timestamp()
                _key = item.get("_key")
                _default = {  # ensuring we do some data can't be overwritten
                    "_key": _key,
                    # "_created_at": ts
                }
                upd, _ = dict_mutator.mutate(mutations=mutations, init_data=item, immuts=self._item._immut_keys, custom_ops=self._custom_ops)
                _data[_key] = {**upd, **_default}
            self._data = self._denormalize_data(_data)
            self._commit()

        elif upsert:
            self.add(mutations)
  
    def delete(self, filters: dict):
        """
        Delete documents based on filters

        Params:
            filters:dict
        """
        _data = self._normalize_data()
        for item in self.find(filters):
            del _data[item.get("_key")]
        self._data = self._denormalize_data(_data)
        self._commit()

    def get(self, _key:str) -> "SubCollectionItem":
        """
        Return a document from subcollection by id 

        Returns: SubCollectionItem
        """
        return self.find_one({"_key": _key})


    def find_one(self, filters:dict={}):
        """
        Return only one item by criteria

        Return:
            dict
        """
        if res := self.find(filters=filters, limit=1):
            return list(res)[0]
        return None 

    def find(self, filters: dict = {}, sorts: dict = {}, limit: int = 10, skip: int = 0) -> dict_query.Cursor:
        """
        Perform a query

        Params:
            filters:
            sorts:
            limit:
            skip:
        """
        sorts = _parse_sort_dict(sorts, False)
        data = [SubCollectionItem(self, d) for d in dict_query.query(data=self._data, filters=filters)]
        return dict_query.Cursor(data, sort=sorts, limit=limit, skip=skip)

    def filter(self, filters: dict = {}) -> dict_query.Cursor:
        """
        Alias to find() but makes it seems fluenty
        
        Returns:
            dict_query:Cursor
        """
        data = dict_query.query(data=self._data, filters=filters)
        return dict_query.Cursor([SubCollectionItem(self, d) for d in data])

class SubCollectionItem(Item_Impl):
    _key = None 

    def __init__(self, subCollection: SubCollection, data):
        self._subcollection = subCollection
        self._load(data)

    @property
    def parent(self):
        """
        Holds parent data
        """
        return self._subcollection._item

    def _update(self, mutations):
        data = dict(self)
        mutations = copy.deepcopy(mutations)
        doc, oplog = dict_mutator.mutate(mutations=mutations, init_data=data, immuts=self.parent._immut_keys, custom_ops=self._subcollection._custom_ops)
        self._subcollection._save(self._key, doc)
        self._load(doc)
        return oplog

    def _load(self, data):
        self._key = data.get("_key")
        super().__init__(data)

#------------------------------------------------------------------------------

class Database(object):
    """
    Angola Database
    """

    def __init__(self,
                 hosts:str=None,
                 username:str="root",
                 password:str=None, 
                 dbname: str = "_system", 
                 client:"Database"= None, 
                 default_indexes:dict={},
                 query_max_limit=100,
                 custom_ops:dict={}):
        """
        
        Params:
            host:str|list
            username:str
            password
            dbname
            client:Database
            default_indexes:dict
            query_max_limit
            custom_ops:dict - 
        
        """

        self.client = client
        self.username = username
        self.password = password
        self.db = None
        self.dbname = dbname
        self.default_indexes = default_indexes
        self.query_max_limit = query_max_limit
        self._custom_ops = custom_ops

        if not self.client:
            self.client = ArangoClient(hosts=hosts, serializer=lib.json_ext.dumps, deserializer=lib.json_ext.loads)

        if self.dbname:
            self.db = self.client.db(name=self.dbname, username=self.username, password=self.password)

    @property
    def aql(self):
        return self.db.aql

    def has_db(self, dbname:str=None) -> bool:
        """
        Check if the system has a database

        Params:
            dbname:str|None - The dbname to check or the current self.dbname

        Returns: 
            bool
        """
        _dbname = dbname or self.dbname
        sys_db = self.use_db("_system")
        return sys_db.db.has_database(_dbname)

    def create_db(self, dbname:str=None) -> "Database":
        """
        Create a database if doesn't exists
        Params:
            dbname:str|None - The dbname to check or the current self.dbname

        Returns:
            Database
        """
        _dbname = dbname or self.dbname
        sys_db = self.use_db("_system")
        if not sys_db.db.has_database(_dbname):
            sys_db.db.create_database(_dbname)
        return self.select_db(_dbname)

    def select_db(self, dbname:str) -> "Database":
        """
        Select a different DB using the same connection

        Params:
            dbname:str - The dbname to check
        Returns: 
            Database

        """
        return Database(client=self.client, dbname=dbname, username=self.username, password=self.password, custom_ops=self._custom_ops)

    def has_collection(self, collection_name) -> bool:
        """
        Test if collection exists in the current db

        Params:
            collection_name:str - the collection name 

        Returns:
            bool
        """
        return self.db.has_collection(collection_name)

    def select_collection(self, collection_name, indexes=None, immut_keys=None, user_defined=True) -> "Collection":
        """
        To select a collection

        Params:
            collection_name:str - collectioin name 
            indexes:List[dict] - the indexes to use
            immut_keys:list - immutable keys. Keys that can't be updated once created

        Return:
            Collection

        """

        if self.has_collection(collection_name):
            col = self.db.collection(collection_name)
        else:
            col = self.db.create_collection(collection_name)
            if not indexes and user_defined is True and self.default_indexes:
                indexes = self.default_indexes
            
            # indexes
            if isinstance(indexes, list) and indexes:
                for index in [*indexes, *DEFAULT_INDEXES]:
                    col._add_index(index) 

        return Collection(db=self, collection=col, immut_keys=immut_keys, custom_ops=self._custom_ops)

    def get_item(self, path:str) -> CollectionItem:
        """
        To get an item via path.

        - Item Path: [COLLECTION_NAME/KEY] -> articles/1234568
        - Item's Subcollection path: [COLLECTION/_KEY/SUBCOLLECTION] -> articles/1234/comments
        - Item's Subcollection sub Item path: [COLLECTION/_KEY/SUBCOLLECTION/_SUB_KEY] -> articles/1234/comments/73992

        Params:
            path:str - str of [collection_name/document_key]
        Return:
            collection.item

        Example:
            db.get_item("articles/somethingf")
        
        Returns:
            CollectionItem

        """

        paths = path.split("/")
        len_paths = len(paths)
        if len_paths < 2 or len_paths > 4:
            raise InvalidItemPathError()

        if len_paths == 2: # item -> [coll/key]
            return self.select_collection(paths[0]).get(paths[1])
        elif len_paths == 3: # item's subcolelction -> [coll/key/subcoll]
            return self.select_collection(paths[0]).get(paths[1]).select_subcollection(paths[2])
        elif len_paths == 4: # item's subcollection items -> [coll/key/subcoll/subkey]
            return self.select_collection(paths[0])\
                .get(paths[1])\
                .select_subcollection(paths[2])\
                .get(paths[3])

    def execute_aql(self, query:str, bind_vars:dict={}, *a, **kw):
        """ 
        Execute AQL 
        Params:
            query:str - the AQL to execute 
            bind_vars: dict - the variables to pass in the query
        Return aql cursor
        """
        return self.aql.execute(query=query, bind_vars=bind_vars, *a, **kw)

    def query(self, xql:lib_xql.XQLDEFINITION, data:dict={}, kvmap:dict={}, parser=None, data_mapper=None) -> QueryResult:
        """
        XQL query  a collection based on filters

        It will return the cursor:ArangoCursor and a pagination for the current state
        
        Params:
            xql:lib_xql.XQLDEFINITION
            data:dict
            kvmap:dict
            data_mapper:function - a callback function
        Returns
            tuple(cursor:ArangoCursor, pagination:dict)
        """
        aql, bind_vars, pager = self.build_query(xql=xql, data=data, kvmap=kvmap, parser=parser)
        cursor = self.execute_aql(aql, bind_vars=bind_vars, count=True, full_count=True)            
        return QueryResult(cursor=cursor, pager=pager, data_mapper=data_mapper)

    def build_query(self, xql:lib_xql.XQLDEFINITION, data:dict={}, kvmap:dict={}, parser=None):
        """
        Build a query from XQL

        Return tuple:
            - aql:str
            - bind_vars:dict
            - pagination:tuple 
                -> tuple(page, per_page)
        """        
        xql = lib_xql.prepare_xql(xql)
        # replace the kvmap
        xql["FILTER"] = lib.dict_find_replace(xql["FILTER"], kvmap)

        # pagination
        if "page" in data:
            xql["PAGE"] = data.get("page") or 1
            del data["page"]
        if "take" in data:
            xql["TAKE"] = data.get("take") or 10
            del data["take"]

        _per_page, _, _page = lib_xql.xql_take_skip_page(xql=xql, max_limit=self.query_max_limit)
        aql, bind_vars = lib_xql.xql_to_aql(xql, vars=data, parser=parser, max_limit=self.query_max_limit)
        bind_vars.update(data)
        return aql, bind_vars, (_page, _per_page)

    def collections(self) -> list:
        """
        All collections in the db

        Returns:
            list
        """
        return self.db.collections()
    
    def rename_collection(self, collection_name:str, new_name:str):
        """
        Rename collection
        """
        if self.has(collection_name) and not self.has(new_name):
            coll = self.select(collection_name)
            coll.rename(new_name)
            return self.select(new_name)
    
    def drop_collection(self, collection_name:str):
        if self.has(collection_name):
            self.db.delete_collection(collection_name)

    def add_index(self, collection_name, data:dict):
        """
        Args:
            - collection, the collection name
            - data: dict of 
                    {
                        "type": "persistent",
                        "fields": [] # list of fields
                        "unique": False # bool - Whether the index is unique
                        "sparse": False # bool,
                        "name": "" # str - Optional name for the index
                        "inBackground": False # bool - Do not hold the collection lock
                    }
        """
        col = self.db.collection(collection_name)
        col._add_index(data)
      
    def delete_index(self, collection_name:str, id):
        """
        Delete Index

        Args:
            - collection, the collection name
            - id: the index id
        """
        col = self.db.collection(collection_name)
        col.delete_index(id, ignore_missing=True)

class Collection(object):

    def __init__(self, db:Database, collection,  immut_keys:list=[], custom_ops:dict={}):
        self.db = db
        self.collection = collection
        self._immut_keys = immut_keys
        self._custom_ops = custom_ops
        self.collection_name = self.collection.name

    def _commit(self, item:CollectionItem):
        """
        Save the item in the db
        """
        if not item._key:
            raise MissingItemKeyError()
        return self.collection.update(item.to_dict(), return_new=True)["new"]

    def __iter__(self):
        return self.find(filters={})

    def item(self, data:dict) -> CollectionItem:
        """
        Load data as item

        Returns:
            CollectionItem
        """
        if not isinstance(data, CollectionItem):
            if "_key" not in data:
                return CollectionItem.new(data, commiter=self._commit, immut_keys=self._immut_keys, custom_ops=self._custom_ops)               
        return CollectionItem(data, commiter=self._commit, immut_keys=self._immut_keys, custom_ops=self._custom_ops)

    def has(self, _key) -> bool: 
        """
        Check if a collection has _key

        Args:
            _key:str

        Returns: 
            Bool
        """
        return self.collection.has(_key)

    def get(self, _key) -> CollectionItem:
        """ 
        Get a document from the collection and returns a collectionItem
        Returns:
            CollectionItem
        """

        if data := self.collection.get(_key):
            return self.item(data)
        return None

    def create(self, data:dict={}) -> CollectionItem:
        """
        To create a new Item without inserting in the collection

        Requires #commit() to save data

        Returns:
            CollectionItem

        Example:
            item = coll.create({...})
            item.commit()
        """
        return CollectionItem.new(data, commiter=self._commit, custom_ops=self._custom_ops)

    def insert(self, data:dict, _key=None) -> CollectionItem:
        """
        To insert a new Item and commit in the collection

        Returns:
            CollectionItem

        Example
            item = coll.insert(...)
        """
        if _key or "_key" in data:
            _key = _key or data["_key"]
            if self.has(_key):
                raise ItemExistsError()
            data["_key"] = _key
        item = data
        if not isinstance(data, CollectionItem):
            item = CollectionItem.new(data, custom_ops=self._custom_ops)
        self.collection.insert(item.to_dict(), silent=True)
        return self.get(item._key) 

    def update(self, _key:str, data:dict) -> CollectionItem:
        """
        Update an item

        Returns
            CollectionItem

        """
        item = self.item({**data, "_key": _key})
        self._commit(item)  
        return self.get(item._key) 

    def upsert(self, data:dict) -> CollectionItem:
        """
        To update or insert data.

        Args:
            data:dict

        Return:
            CollectionItem
        """

        if "_key" in data:
            if self.has(data["_key"]):
                _key = data.pop("_key")
                return self.update(_key=_key, data=data)
        return self.insert(data)

    def delete(self, _key):
        """
        Delete a document by _key
        """
        self.collection.delete(_key)

    def find(self, filters:dict, skip=None, limit=None):
        """
        Perform a find in the collections

        Returns
            Generator[CollectionItem]
        """

        xql = {
            "FROM": self.name, 
            "FILTER": filters,
            "SKIP": skip,
            "TAKE": limit
        }

        def data_mapper(item): return self.item(item)
        return self.db.query(xql, data_mapper=data_mapper)

    def find_one(self, filters:dict):
        """
        Retrieve one item based on the criteria

        Returns
            CollectionItem
        """
        if data := list(self.find(filters=filters, limit=1)):
            return data[0]
        return None

#------------------------------------------------------------------------------

def _create_document_item(data:dict={}) -> dict:
    _key = data["_key"] if "_key" in data else lib.gen_key()

    return {
        **data,
        "_key": _key,
        "_created_at:$currdate": True,
        "_modified_at": None
    }


def _ascdesc(v, as_str=True):
    if as_str:
        if isinstance(v, int):
            return "DESC" if v == -1 else "ASC"
    else:
        if isinstance(v, str):
            return -1 if v.upper() == "DESC" else 1
    return v


def _parse_sort_dict(sorts: dict, as_str=True):
    return [(k, _ascdesc(v, as_str)) for k, v in sorts.items()]

