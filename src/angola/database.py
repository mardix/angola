#-----------------------------
# -- Angola --
#-----------------------------

import copy 
from typing import Any, List
from arango import ArangoClient
from arango.exceptions import ArangoError, DocumentUpdateError
from contextlib import contextmanager
from . import lib, lib_xql, dict_mutator, dict_query


DEFAULT_INDEXES = [
    {
        "type": "persistent",
        "fields": ["_created_at"],
        "name": "idx00__created_at"
    },
    {
        "type": "persistent",
        "fields": ["_modified_at"],
        "name": "idx00__modified_at"
    },
    {
        "type": "ttl",
        "fields": ["__ttl"],
        "name": "idx00__ttl",
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

class CollectionActiveRecordMixin(object):
    """
    CollectionActiveRecordMixin

    An abstraction class to use as an active record on the items

    Usage:

      class User(CollectionActiveRecordMixin):
        def full_name(self):
            return "%s %s" % (self.get("first_name), self.get("last_name"))
            
      coll = #db.select_collection(..., item_class=User)

      if item := coll.get(_key):
        print(item.full_name())

    """
    _item = None

    def __init__(self, _item, *a, **kw):
        self._item = _item


    def __call__(self, _item=None, *a, **kw):
        i = copy.deepcopy(self)
        i._item = _item
        return i

    def __getattr__(self, __name: str, *a, **kw):
      return self._item.__getattribute__(__name, *a, **kw)

   
#------------------------------------------------------------------------------

class _QueryResultIterator(object):
    results:list = []
    pagination:dict = {}
    cursor:list = []
    count:int = 0
    size:int = 0

    def __init__(self, cursor, pager, data_mapper=None):
        self.cursor = cursor
        stats = cursor.statistics()
        self.count = self.cursor.count() # current count
        self.size = stats["fullCount"] # total count
        self.pagination = lib.gen_pagination(
                                            size=self.size,
                                            count=self.count,
                                            page=pager[0],
                                            per_page=pager[1])

        def _default_data_mapper_cb(item): return item 
    
        _data_mapper = _default_data_mapper_cb if not data_mapper else data_mapper

        self.results = [_data_mapper(item) for item in self.cursor]

    def __iter__(self):
        """
        Iterate over the results
        """
        yield from self.results

    def __len__(self):
        """
        Get the total results 
        """
        return self.size

class _ItemMixin(dict):
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

    def rename(self, path: str, value:str):
        """ 
        RENAME: Rename a property by key/DotNotation and return the value

        Params:
            path:str - The source
            value:str - the target value

        Returns:
            Any: the value that was removed
        """
        path = self._make_path(path)
        self._update({"%s:$rename" % path: value})

    def copy(self, path: str, value:str):
        """ 
        COPY: Copy a property by key/DotNotation and return the value

        Params:
            path:str - The source
            value:str - the target value
        """
        path = self._make_path(path)
        self._update({"%s:$copy" % path: value})

    def xadd(self, path: str, values):
        """
        XADD: Add *values if they don't exist yet

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
        XADD: Add *values if they don't exist yet

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
        XREM: Remove items from a list

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
        XREM: Remove items from a list

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
        XPUSH: push item to the right of list. 

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
        XPUSH_MANY: push item to the right of list. 

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
        XPUSHL: push item to the right of list. 

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

    def timestamp(self, path:str, value:Any=True):
        op = "%s:$timestamp" % self._make_path(path)
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

class CollectionItem(_ItemMixin):
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

    # _read_only. When read_only, it can update 
    _read_only = False

    @classmethod
    def new(cls, data:dict, immut_keys:list=[], db=None, collection=None, commiter=None, custom_ops:dict={}, read_only:bool=False):
      return cls(data=_create_document_item(data), db=db, collection=collection, immut_keys=immut_keys, commiter=commiter, custom_ops=custom_ops, read_only=read_only)

    def __init__(self, data: dict, db=None, collection=None, immut_keys:list=[], load_parser=None, commiter=None, custom_ops:dict={}, read_only:bool=False):
        if "_key" not in data:
            raise MissingItemKeyError()
        self._db = db
        self._collection = collection
        self._load_parser = load_parser
        self._commiter = commiter
        self._immut_keys = immut_keys
        self._cx = False
        self._custom_ops = custom_ops
        self._read_only = read_only
    
        data, _ = dict_mutator.mutate(mutations=data,  immuts=immut_keys, custom_ops=self._custom_ops)
        self._load(data)

    def to_dict(self):
        data = dict(self)
        if self._subcollections:
            data["__subcollections"] = self._subcollections
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
        sc = SubCollection(item=self, name=name, custom_ops=self._custom_ops, constraints=constraints)
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
        return SubCollection(item=self, name=name, custom_ops=self._custom_ops, constraints=constraints)

    def get_item(self, path:str) -> "_SubCollectionItem":
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
            _SubCollectionItem

        """
        
        paths = path.split("/")
        if len(paths) != 2:
            raise InvalidItemPathError()

        return self.select_subcollection(paths[0]).get(paths[1])        

    @property
    def subcollections(self) -> list:
        """ List all collections """
        return list(self._subcollections.keys())

    def drop_subcollection(self, name: str):
        try:
            if name in self._subcollections:
                del self._subcollections[name]
            self.set("__subcollections", self._subcollections)
        except KeyError as _:
            pass
        return True

    def _set_subcollection(self, name:str, data:Any):
        self._subcollections[name] = data
        self.set("__subcollections", self._subcollections)

    def commit(self) -> "Self":
        """ To save """

        if self._read_only:
            return self
        
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
        
        if self._read_only:
            return self
        
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
        if "__subcollections" in item:
            self._subcollections = item.pop("__subcollections") or {}

        if "_key" in item:
            self._key = item.get("_key")
        super().__init__(item)

    def _clear_self(self):
        """ clearout all properties """
        for _ in list(self.keys()):
            if _ in self:
                del self[_]

    def link(self, to_item:"CollectionItem", data={}, edge_collection_name=None):
        """
        ::Graph::

        Create a graph link between this item and to_item
        """
        return self._db.link_edges(from_item=self, to_item=to_item, data=data, edge_collection_name=edge_collection_name)

    def traverse(self, collection:"Collection", relations:list("Collection")=None, direction="outbound"): 
        return self._db.traverse(from_item=self, collection=collection, relations=relations, direction=direction)

    def set_ttl(self, nattime:str) -> "Self":
        """
        To set a time to live on an item
        ie: 
            item.set_ttl("2days")

            to reset the ttl
                item.set_ttl(False)

        Params:
            - nattime:str - Natural time - ie 1hour, 60seconds

        Returns:
            self
        """
        if isinstance(nattime, str):
            self.update({"__ttl:$timestamp": nattime})
        elif nattime is False:
            self.update({"__ttl": None})
        return self

    def delete(self) -> bool:
        """
        To delete an item
        Todo: deleted links/edges
        """
        self._collection.delete(self._key)
        return True

    def get_sizeof(self) -> int:
        """
        Get the size of the document

        Returns: int
        """
        return lib.get_sizeof(self.to_dict())

class _SubCollectionItem(_ItemMixin):
    _key = None 

    def __init__(self, subCollection: "SubCollection", data):
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

    def delete(self):
        self._subcollection.delete({"_key": self._key})
        return True
     
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Database(object):
    """
    Angola Database
    """
    SYSTEM_DB = "_system"

    def __init__(self,
                 hosts:str=None,
                 username:str="root",
                 password:str=None, 
                 dbname: str = SYSTEM_DB, 
                 client:"Database"= None, 
                 default_indexes:list=[],
                 query_max_limit=100,
                 collection_prefix:str=None,
                 custom_ops:dict={}):
        """
        
        Params:
            host:str|list
            username:str
            password
            dbname
            client:Database
            default_indexes:list
            query_max_limit
            collection_prefix:str|function - a prefix to add in all collection name
            custom_ops:dict - 
        
        """

        self.client = client
        self.username = username
        self.password = password
        self.db = None
        self.dbname = dbname or self.SYSTEM_DB # fallback to _system_db
        self.default_indexes = default_indexes
        self.query_max_limit = query_max_limit
        self._custom_ops = custom_ops
        self._collection_prefix = collection_prefix

        if not self.client:
            self.client = ArangoClient(hosts=hosts, serializer=lib.json_ext.dumps, deserializer=lib.json_ext.loads)

        if self.dbname:
            self.db = self.client.db(name=self.dbname, username=self.username, password=self.password)

    @property
    def aql(self):
        return self.db.aql

    def _prefix_collection_name(self, collection_name:str) -> str:
        if self._collection_prefix:
            if isinstance(self._collection_prefix, str):
                collection_name = "%s%s" % (self._collection_prefix, collection_name)
            elif callable(self._collection_prefix):
                collection_name = self._collection_prefix(collection_name)
        return collection_name

    def has_db(self, dbname:str=None) -> bool:
        """
        Check if the system has a database

        Params:
            dbname:str|None - The dbname to check or the current self.dbname

        Returns: 
            bool
        """
        _dbname = dbname or self.dbname
        sys_db = self.select_db("_system")
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
        sys_db = self.select_db("_system")
        if not sys_db.db.has_database(_dbname):
            sys_db.db.create_database(_dbname)
        return self.select_db(_dbname)

    def select_db(self, dbname:str, collection_prefix:str=None, default_indexes:dict=None) -> "Database":
        """
        Select a different DB using the same connection

        Params:
            dbname:str - The dbname to check
            collection_prefix
            default_indexes
        Returns: 
            Database
        """
        return Database(client=self.client, 
                        dbname=dbname, 
                        username=self.username, 
                        password=self.password, 
                        collection_prefix=collection_prefix or self._collection_prefix, 
                        custom_ops=self._custom_ops, 
                        default_indexes=default_indexes or self.default_indexes,
                        query_max_limit=self.query_max_limit)

    def has_collection(self, collection_name) -> bool:
        """
        Test if collection exists in the current db. 

        Params:
            collection_name:str - the collection name 

        Returns:
            bool
        """
        collection_name = self._prefix_collection_name(collection_name)
        return self.db.has_collection(collection_name)

    def create_collection(self, collection_name:str, indexes:list=[]) -> bool:
        """
        Create a collection if not exists
        Returns: bool
        """
        if not self.has_collection(collection_name):
            collection_name = self._prefix_collection_name(collection_name)
            col = self.db.create_collection(collection_name)

            _indexes = DEFAULT_INDEXES
            if not indexes and self.default_indexes:
                _indexes = [*self.default_indexes, *_indexes]

            for index in _indexes:
                col._add_index(index) 
                
            return True 
        return False

    def select_collection(self, collection_name:str, indexes:list=[], immut_keys:list=[], item_class=None, auto_create:bool=True) -> "Collection":
        """
        To select a collection

        Params:
            collection_name:str - collectioin name 
            indexes:List[dict] - the indexes to use
            immut_keys:list - immutable keys. Keys that can't be updated once created
            auto_create:bool - To auto create the collection if doesn't exist

        Return: Collection

        """

        if self.has_collection(collection_name):
            collection_name = self._prefix_collection_name(collection_name)
            col = self.db.collection(collection_name)
        elif auto_create is True:
            self.create_collection(collection_name=collection_name, indexes=indexes)
            collection_name = self._prefix_collection_name(collection_name)
            col = self.db.collection(collection_name)
        else:
            raise CollectionNotFoundError()

        return Collection(db=self, collection=col, immut_keys=immut_keys, custom_ops=self._custom_ops, item_class=item_class)

    def select_edge_collection(self, collection_name:str):
        if self.db.has_collection(collection_name):
            collection_name = self._prefix_collection_name(collection_name)
            return self.db.collection(collection_name)
        else:
            collection_name = self._prefix_collection_name(collection_name)
            return self.db.create_collection(name=collection_name, edge=True)

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

        try:
            if len_paths == 2: # item -> [coll/key]
                return self.select_collection(self._prefix_collection_name(paths[0])).get(paths[1])
            elif len_paths == 3: # item's subcolelction -> [coll/key/subcoll]
                return self.select_collection(self._prefix_collection_name(paths[0])).get(paths[1]).select_subcollection(paths[2])
            elif len_paths == 4: # item's subcollection items -> [coll/key/subcoll/subkey]
                return self.select_collection(self._prefix_collection_name(paths[0]))\
                    .get(paths[1])\
                    .select_subcollection(paths[2])\
                    .get(paths[3])
        except Exception as e:
            return None

    def execute_aql(self, query:str, bind_vars:dict={}, *a, **kw):
        """ 
        Execute AQL 
        Params:
            query:str - the AQL to execute 
            bind_vars: dict - the variables to pass in the query
        Return aql cursor
        """
        print("AQL", query, bind_vars)
        print()
        return self.aql.execute(query=query, bind_vars=bind_vars, *a, **kw)

    def query(self, xql:lib_xql.XQLDEFINITION, data:dict={}, kvmap:dict={}, parser=None, data_mapper=None) -> _QueryResultIterator:
        """
        XQL query  a collection based on filters

        It will return the cursor:ArangoCursor and a pagination for the current state
        
        Params:
            xql:lib_xql.XQLDEFINITION
            data:dict
            kvmap:dict
            data_mapper:function - a callback function
        Returns
            _QueryResultIterator
        """

        aql, bind_vars, pager = self._build_query(xql=xql, data=data, kvmap=kvmap, parser=parser)
        cursor = self.execute_aql(aql, bind_vars=bind_vars, count=True, full_count=True)            
        return _QueryResultIterator(cursor=cursor, pager=pager, data_mapper=data_mapper)

    def _build_query(self, xql:lib_xql.XQLDEFINITION, data:dict={}, kvmap:dict={}, parser=None):
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
        xql["FILTERS"] = lib.dict_find_replace(xql["FILTERS"], kvmap)

        # pagination
        if "page" in data:
            xql["PAGE"] = data.get("page") or 1
            del data["page"]
        if "limit" in data:
            xql["LIMIT"] = data.get("limit") or 10
            del data["limit"]

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
            collection_name = self._prefix_collection_name(collection_name)
            new_name = self._prefix_collection_name(new_name)
            coll = self.select(collection_name)
            coll.rename(new_name)
            return self.select(new_name)
    
    def drop_collection(self, collection_name:str):
        if self.has_collection(collection_name):
            collection_name = self._prefix_collection_name(collection_name)
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
        collection_name = self._prefix_collection_name(collection_name)
        col = self.db.collection(collection_name)
        col._add_index(data)
      
    def delete_index(self, collection_name:str, id):
        """
        Delete Index

        Args:
            - collection, the collection name
            - id: the index id
        """
        collection_name = self._prefix_collection_name(collection_name)
        col = self.db.collection(collection_name)
        col.delete_index(id, ignore_missing=True)

    def link_edges(self, from_item:"CollectionItem", to_item:"CollectionItem", data:dict={}, edge_collection_name:str=None):
        """
        GRAPH
        Link edges of 2 collections from:to

        Params:
            - from_item:CollectionItem
            - to_item:CollectionItem
            - data:dict
            - edge_collection_name:str
        """
        from_coll_name = from_item._collection.name
        to_coll_name = to_item._collection.name

        if not edge_collection_name and from_coll_name and to_coll_name:
            edge_collection_name = "edges__%s--%s" % (from_coll_name, to_coll_name)
        if not edge_collection_name:
            raise Exception("MISSING EDGE COLLECTION NAME")

        coll = self.select_edge_collection(edge_collection_name)

        # ensuring _id and _key are not included
        if data:
            for k in ["_id", "_key"]:
                if k in data:
                    data.pop(k)
        doc = {
            **data,
            "_from": "%s/%s" % (from_coll_name, from_item._key),
            "_to": "%s/%s" % (to_coll_name, to_item._key)
        }

        # update edge if exists, otherwise insert
        edge = list(coll.find({"_from": doc["_from"], "_to": doc["_to"]}, limit=1))
        if edge:
            return coll.update({**data, "_id": edge[0]["_id"]})
        else:
            return coll.insert(doc)

    def unlink_edges(self, from_item:"CollectionItem", to_item:"CollectionItem"):
        pass

    def _load_item(self, data:dict) -> "CollectionItem":
        if "_id" in data:
            collection_name, _key = data.get("_id").split("/")
            collection_name = self._prefix_collection_name(collection_name)
            col = self.db.collection(collection_name)
            return Collection(db=self, collection=col, custom_ops=self._custom_ops).item(data)
        else:
            raise Exception("INVALID_ITEM__MUST_HAVE_ID")

    def traverse(self, from_item:"CollectionItem", collection:"Collection", relations:list("Collection")=None, direction="outbound", filters={}):
        """
        == GRAPH == 
        To traverse 

        Params:
            - from_item:CollectionItem - The item to traverse from
            - collection: Collection
            - relations:list[Collection.link]

        Example:
            item = $coll.get("_key")
            traversial = $coll.traverse(from_item=item, collection=$collectionInstance2)
            for e in traversial:
                item_, second_item = e

            #== Advanced, 4 depth. # the deeper relation the more the data
            item = $coll.get("_key")
            relations = [ $collInstance2.link($collInstance3), $collInstance3.link($collInstance4)]
            traversial = $coll.traverse(from_item=item, collection=$collectionInstance2)
            for e in traversial:
                item_, second_item, third_item, fourth_item = e
            


        AQL:
            FOR v, e, p in 2..3 OUTBOUND "test_country/01gm1g1wed20nf0d835m8k963k" 
            GRAPH "graph__edges__test_country--test_region--test_region--test_city"
            FILTER p.vertices[1].name == "SC"
            RETURN p
        """

        _key = from_item._key

        if not collection:
            raise Exception("Missing")

        min_depth = 1
        defs = []
        edge_name = "edges__%s" % from_item._collection.name
        edge_name += "--%s" % collection.collection_name
        defs.append({
            "edge_collection": _create_edge_name(from_name=from_item._collection.name, to_name=collection.collection_name),
            "from_vertex_collections": [from_item._collection.name],
            "to_vertex_collections": [collection.collection_name]
        })    

        # Add more relations
        if relations:
            min_depth += len(relations)
            for collection_def in relations:
                edge_name += "--%s" % collection_def[0]
                defs.append({
                    "edge_collection": collection_def[1],
                    "from_vertex_collections": [collection_def[2]],
                    "to_vertex_collections": [collection_def[3]]
                })

        graph_name = "graph__%s" % edge_name
        start_vertex = "%s/%s" % (from_item._collection.name, _key)

        if self.db.has_graph(graph_name):
            graph = self.db.graph(graph_name)
        else:
            graph = self.db.create_graph(name=graph_name, edge_definitions=defs)

        for trav in graph.traverse(start_vertex=start_vertex,
                                    direction=direction,
                                    strategy='bfs',
                                    edge_uniqueness='global',
                                    vertex_uniqueness='global',
                                    min_depth=min_depth, 
                                    )["paths"]:
                
                yield tuple(self._load_item(item) for item in trav["vertices"])


class Collection(object):

    def __init__(self, db:Database, collection,  immut_keys:list=[], custom_ops:dict={}, item_class=None):
        self.db = db
        self.collection = collection
        self._immut_keys = immut_keys
        self._custom_ops = custom_ops
        self.collection_name = self.collection.name
        self.item_class = item_class

    def _commit(self, item:CollectionItem, replace_document=False):
        """
        To commit/save changes

        Params:
            item:CollectionItem
            replace_document:bool - To replace instead of updating. Replace will not merge the data.
        """
        if not item._key:
            raise MissingItemKeyError()
        try:
            if replace_document:
                return self.collection.replace(item.to_dict(), return_new=True)["new"]
            else:
                item.timestamp('_modified_at')
                return self.collection.update(item.to_dict(), return_new=True)["new"]
        except DocumentUpdateError as due:
            item.update({"_modified_at": None})
            return self.collection.insert(item.to_dict(), return_new=True)["new"]

    def __iter__(self):
        return self.find(filters={})

    def item(self, data:dict, read_only:bool=False) -> CollectionItem:
        """
        Load data as item

        Returns:
            CollectionItem
        """
        item = None
        if not isinstance(data, CollectionItem) and "_key" not in data:
            item = CollectionItem.new(data, db=self.db, collection=self.collection, commiter=self._commit, immut_keys=self._immut_keys, custom_ops=self._custom_ops)               
        else:
            item = CollectionItem(data, db=self.db, collection=self.collection, commiter=self._commit, immut_keys=self._immut_keys, custom_ops=self._custom_ops, read_only=read_only)

        return self.item_class(item) if item and self.item_class else item

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
        return CollectionItem.new(data, db=self.db, collection=self.collection, commiter=self._commit, custom_ops=self._custom_ops)

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
            item = CollectionItem.new(data, db=self.db, collection=self.collection, custom_ops=self._custom_ops)
        self.collection.insert(item.to_dict(), silent=True)
        return self.get(item._key) 

    def update(self, _key:str, data:dict, replace_document=False) -> CollectionItem:
        """
        To update and item. Can also replace the item

        Params:
            _key:str - document key 
            data:dict - data to update
            replace_document:bool - If true will replace the document and not merge

        Returns
            CollectionItem

        """
        item = self.item({**data, "_key": _key})
        self._commit(item, replace_document=replace_document)  
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

    def find(self, filters:dict={}, offset=None, limit=10, sort=None, page=None, xql:dict=None):
        """
        Perform a find in the collections

        Returns
            Generator[CollectionItem]
        """
        
        if page is None and offset:
            page = lib.calc_pagination_page_from_offset(offset=offset, per_page=limit)

        elif offset is None and page:
            offset = lib.calc_pagination_offset(page=page, per_page=limit)

        read_only = False
        _xql = {
            "FROM": self.collection_name, 
            "FILTERS": filters,
            "OFFSET": offset,
            "LIMIT": limit,
            "SORT": sort,
            "PAGE": page
        }

        # Extended XQL
        if xql:
            _xql.update(xql)
            if "JOIN" in _xql:
                read_only = True


        def data_mapper(item): return self.item(item, read_only=read_only)
        return self.db.query(_xql, data_mapper=data_mapper)

    def find_one(self, filters:dict, sort=None):
        """
        Retrieve one item based on the criteria

        Returns
            CollectionItem
        """
        if data := list(self.find(filters=filters, limit=1, sort=None)):
            return data[0]
        return None

    def edges_with(self, collection:"Collection") -> tuple:
        """
        ::GRAPH::

        Create an Edge Collection Definition, especially when building a traversal

        ie:
        relations = [CollectionA.edges_with(CollectionB)]

        Returns
            tuple(name, edge_name, from_collection_name, to_collection_name)
        """
        edge_name = _create_edge_name(from_name=self.collection_name, to_name=collection.collection_name)
        name = "%s--%s" % (self.collection_name, collection.collection_name)
        return (name, edge_name, self.collection_name, collection.collection_name)


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

        item = _create_subdocument_item(data)
        self._data.append(item)
        self._commit()
        return _SubCollectionItem(self, item)

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
            self.insert(mutations)
  

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

    def get(self, _key:str) -> "_SubCollectionItem":
        """
        Return a document from subcollection by id 

        Returns: _SubCollectionItem
        """
        return self.find_one({"_key": _key})

    def find_one(self, filters:dict={}) -> "_SubCollectionItem":
        """
        Return only one item by criteria

        Return:
            dict
        """
        if res := self.find(filters=filters, limit=1):
            return list(res)[0]
        return None 

    def find(self, filters: dict = {}, sort: dict = {}, limit: int = 10,  offset:int=0, page=None) -> dict_query.Cursor:
        """
        Perform a query

        Params:
            filters:
            sort:
            limit:
            offset:
        """

        if offset is None and page:
            offset = lib.calc_pagination_offset(page=page, per_page=limit)

        sort = _parse_sort_dict(sort, False)
        data = [_SubCollectionItem(self, d) for d in dict_query.query(data=self._data, filters=filters)]
        return dict_query.Cursor(data, sort=sort, limit=limit, offset=offset)

    def filter(self, filters: dict = {}) -> dict_query.Cursor:
        """
        Alias to find() but makes it seems fluenty
        
        Returns:
            dict_query:Cursor
        """
        data = dict_query.query(data=self._data, filters=filters)
        return dict_query.Cursor([_SubCollectionItem(self, d) for d in data])


#------------------------------------------------------------------------------

def _create_edge_name(from_name, to_name):
    return "edges__%s--%s" % (from_name, to_name)

def _create_document_item(data:dict={}) -> dict:
    _key = data["_key"] if "_key" in data else lib.gen_key()

    return {
        "_key": _key,
        "_created_at:$timestamp": True,
        "_modified_at": None,
        "__ttl": None,
        **data,
    }

def _create_subdocument_item(data:dict={}) -> dict:
    _key = data["_key"] if "_key" in data else lib.gen_key()

    return {
        "_key": _key,
        "_created_at:$timestamp": True,
        "_modified_at": None,
        **data,
    }

def _ascdesc(v, as_str=True):
    if as_str:
        if isinstance(v, int):
            return "DESC" if v == -1 else "ASC"
    else:
        if isinstance(v, str):
            return -1 if v.upper() == "DESC" else 1
    return v


def _parse_sort_dict(sort: dict, as_str=True):
    return [(k, _ascdesc(v, as_str)) for k, v in sort.items()]

