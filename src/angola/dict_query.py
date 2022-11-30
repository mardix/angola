#-----------------------------
# -- Angola --
#-----------------------------

import copy
from . import lib 
from math import ceil
from typing import Any, List


# Map filter
# Map filter operators with their functions
QUERY_FILTERING_MAPPER = {
    '=': '_is_equal',
    'eq': '_is_equal',
    '!=': '_is_not_equal',
    'neq': '_is_not_equal',
    '>': '_is_greater',
    'gt': '_is_greater',
    '<': '_is_smaller',
    'lt': '_is_smaller',
    '>=': '_is_greater_equal',
    'gte': '_is_greater_equal',
    '<=': '_is_smaller_equal',
    'lte': '_is_smaller_equal',
    'in': '_is_in',
    'notin': '_is_not_in',
    'null': '_is_null',
    'notnull': '_is_not_null',
    'startswith': '_is_starts_with',
    'endswith': '_is_ends_with',
    'includes': '_is_includes',
    'between': "_is_between",
    'contains': '_is_contains',
    'exists': '_is_exists',
    'notexists': '_is_not_exists',

}

# FILTER_OPERATOR:
FILTER_OPERATOR = ":$"

# SQL_OPERATORS: valid/strict operators for SQL
SQL_OPERATORS = {
    "eq": "= ?",
    "ne": "!= ?",
    "lt": "< ?",
    "gt": "> ? ",
    "lte": "<= ?",
    "gte": ">= ? ",
    "between": "BETWEEN ? AND ?",
}

class _Undefined: pass

"""
DictQuery

This library helps filter sub document in a list of dict 

:USAGE

data = List[dict]
data = [
    {
        "location": "USA",
        "age": 21,
        "email": "something@this.io",
        "friends": [
            {
                "name": "Jacob",
                "city": "Charlotte",

            }
        ]
    },
    ...
]


filters = {
    "location": "USA",
    "age:$gte": 18,
    "email:$endswith": ".io",
    "friends[*].city:$in": ["Charlotte", "Atlanta"]
}

filtered_data = DictQuery(data).execute(filter)

"""
class DictQuery(object):

    def __init__(self, data: list):

        if not isinstance(data, list):
            raise TypeError("Provided Data is not list")
        self._data = self._flatten_data_list(data)

    def execute(self, filters) -> list:
        self._reset_queries()
        self._build_queries(filters)
        return self._unflatten_data_list(self._execute_queries(self._data, self._queries))
 
    def _flatten_data_list(self, data):
        return [lib.flatten_dict(d) for d in data] if isinstance(data, list) else []

    def _unflatten_data_list(self, data):
        return [lib.unflatten_dict(d) for d in data] if isinstance(data, list) else []

    def _reset_queries(self):
        """ 
        Reset previous query data 
        """
        self._queries = []
        self._current_query_index = 0

    def _store_query(self, query_items):
        """Make where clause

        :@param query_items
        :@type query_items: dict
        """
        temp_index = self._current_query_index
        if len(self._queries) - 1 < temp_index:
            self._queries.append([])
        self._queries[temp_index].append(query_items)
 
    def _execute_queries(self, data:list, queries:list):
        """
        Args:
            data:list
        """
        _matcher = _Matcher()
       
        def func(item):
            or_check = False
            for queriesx in queries:
                and_check = True
                for query in queriesx:
                    _qk = query.get("key")

                    # Filter sub-list using `[*].` 
                    # /basepath/something[*].x
                    if "[*]." in _qk:    
                        and_check2 = False                    
                        basepath, subpath = _qk.split("[*].")
                        subdata = item.get(basepath)
                        if subdata:
                            for subitem in subdata:
                                and_check2 |= _matcher._match(
                                    subitem.get(subpath, _Undefined),
                                    query.get('operator'),
                                    query.get('value'),
                                    query.get('case_insensitive')
                                )    
                        and_check &= and_check2
                    
                    # regular query
                    else:
                        and_check &= _matcher._match(
                            item.get(_qk, _Undefined),
                            query.get('operator'),
                            query.get('value'),
                            query.get('case_insensitive')
                        )
                    
                or_check |= and_check
            return or_check

        return list(filter(lambda item: func(item), data))

    def _where(self, key, operator, value, case_insensitive=False):
        """Make where clause

        :@param key
        :@param operator
        :@param value
        :@type key,operator,value: string

        :@param case_insensitive
        :@type case_insensitive: bool

        :@return self
        """
        self._store_query({
            "key": key,
            "operator": operator,
            "value": value,
            "case_insensitive": case_insensitive
        })

        return self

    def _or_where(self, key, operator, value):
        """Make _or_where clause

        :@param key
        :@param operator
        :@param value
        :@type key, operator, value: string

        :@return self
        """
        if len(self._queries) > 0:
            self._current_query_index += 1
        self._store_query({"key": key, "operator": operator, "value": value})
        return self

    def _build_queries(self, filters: dict) -> tuple:
        """
        Create a FILTER clause

        Params:
            filters: dict
                {
                    'name': 'something',
                    'age:$gt': 18,
                    'cities:$in': ['charlotte', 'Concord'],
                    '$or': [
                        {
                            "cities:$in": [],
                            "_perms.read:$in":[] 
                        }
                    ]
                }
        """

        for k in filters:
            if k.startswith("$"):
                k_ = k.lower()
                # operation
                if k_ in ["$or"] and isinstance(filters[k], (dict, list)):
                    fk = filters[k]
                    if isinstance(fk, dict):
                        fk = [fk]
                    for k0 in fk:
                        for k2 in k0:
                            self._build_query_row(k2, k0[k2], _or=True)
                else:
                    raise Exception("Invalid logic: %s" % k)
            else:
                self._build_query_row(k, filters[k])

    def _build_query_row(self, k: str, value: Any, _or: bool = False):
        operator = "$eq"  # default operator
        if ":" in k:
            k, operator = k.split(":", 2)
            operator = operator.lower()
        operator = operator.replace("$", "")

        if _or:
            self._or_where(k, operator, value)
        self._where(k, operator, value)

class _Matcher(object):
    """docstring for Helper."""
    MAP = QUERY_FILTERING_MAPPER

    def _is_equal(self, x, y):
        return x == y

    def _is_not_equal(self, x, y):
        return x != y

    def _is_greater(self, x, y):
        return x > y

    def _is_smaller(self, x, y):
        return x < y

    def _is_greater_equal(self, x, y):
        return x >= y

    def _is_smaller_equal(self, x, y):
        return x <= y

    def _is_in(self, key, arr):
        return isinstance(arr, list) and \
            bool(len(([k for k in key if k in arr]
                 if isinstance(key, list) else key in arr)))

    def _is_not_in(self, key, arr):
        return isinstance(arr, list) and (key not in arr)

    def _is_null(self, x, y=None):
        return x is None

    def _is_not_null(self, x, y=None):
        return x is not None

    def _is_starts_with(self, data, val):
        if not isinstance(data, str):
            return False
        return data.startswith(val)

    def _is_ends_with(self, data, val):
        if not isinstance(data, str):
            return False
        return data.endswith(val)

    def _is_includes(self, ldata, val):
        if isinstance(ldata, (list, dict, str)):
            return val in ldata
        return False

    def _is_between(self, data, val):
        # TODO: IMPLEMENT
        return False
        
    def _is_contains(self, data, val):
        # TODO: IMPLEMENT
        return False

    def _is_exists(self, data, val=None):
        return data is not _Undefined

    def _is_not_exists(self, data, val=None):
        return data is _Undefined



    def _to_lower(self, x, y):
        return [[v.lower() if isinstance(v, str) else v for v in val]
                if isinstance(val, list) else val.lower()
                if isinstance(val, str) else val
                for val in [x, y]]

    def _match(self, x, op, y, case_insensitive):
        """Compare the given `x` and `y` based on `op`

        :@param x, y, op, case_insensitive
        :@type x, y: mixed
        :@type op: string
        :@type case_insensitive: bool

        :@return bool
        :@throws ValueError
        """
        if (op not in self.MAP):
            raise ValueError('Invalid where condition given: %s' % op)

        if case_insensitive:
            x, y = self._to_lower(x, y)

        func = getattr(self, self.MAP.get(op))
        return func(x, y)


class Cursor(object):

    def __init__(self, cursordat: list, sort=None, skip=None, limit=None):
        """Initialize the mongo iterable cursor with data"""
        self.cursordat = cursordat or []
        self.cursorpos = -1

        if len(self.cursordat) == 0:
            self.currentrec = None
        else:
            self.currentrec = self.cursordat[self.cursorpos]

        if sort:
            self.sort(sort)

        self.paginate(skip=skip, limit=limit)

    def __getitem__(self, key):
        """Gets record by index or value by key"""
        if isinstance(key, int):
            return self.cursordat[key]
        return self.currentrec[key]

    def __len__(self):
        return self.count
        
    def paginate(self, skip=None, limit=None):
        """Paginate list of records"""
        if not self.count or not limit:
            return
        skip = skip or 0
        pages = int(ceil(self.count / float(limit)))
        limits = {}
        last = 0
        for i in range(pages):
            current = limit * i
            limits[last] = current
            last = current
        # example with count == 62
        # {0: 20, 20: 40, 40: 60, 60: 62}
        if limit and limit < self.count:
            limit = limits.get(skip, self.count)
            self.cursordat = self.cursordat[skip: limit]

        return self

    def limit(self, limit=None, skip=None):
        self.paginate(limit=limit, skip=skip)
        return self

    def _order(self, value, is_reverse=None):
        """Parsing data to a sortable form
        By giving each data type an ID(int), and assemble with the value
        into a sortable tuple.
        """

        def _dict_parser(dict_doc):
            """ dict ordered by:
            valueType_N -> key_N -> value_N
            """
            result = list()
            for key in dict_doc:
                data = self._order(dict_doc[key])
                res = (data[0], key, data[1])
                result.append(res)
            return tuple(result)

        def _list_parser(list_doc):
            """list will iter members to compare
            """
            result = list()
            for member in list_doc:
                result.append(self._order(member))
            return result

        # (TODO) include more data type
        if value is None or not isinstance(value, (dict,
                                                   list,
                                                   str,
                                                   bool,
                                                   float,
                                                   int)):
            # not support/sortable value type
            value = (0, None)

        elif isinstance(value, bool):
            value = (5, value)

        elif isinstance(value, (int, float)):
            value = (1, value)

        elif isinstance(value, str):
            value = (2, value)

        elif isinstance(value, dict):
            value = (3, _dict_parser(value))

        elif isinstance(value, list):
            if len(value) == 0:
                # [] less then None
                value = [(-1, [])]
            else:
                value = _list_parser(value)

            if is_reverse is not None:
                # list will firstly compare with other doc by it's smallest
                # or largest member
                value = max(value) if is_reverse else min(value)
            else:
                # if the smallest or largest member is a list
                # then compaer with it's sub-member in list index order
                value = (4, tuple(value))

        return value

    def sort(self, key_or_list, direction=None):
        """
        Sorts a cursor object based on the input
        :param key_or_list: a list/tuple containing the sort specification,
        i.e. ('user_number', -1), or a basestring
        :param direction: sorting direction, 1 or -1, needed if key_or_list
                          is a basestring
        :return:
        """

        # checking input format

        sort_specifier = list()
        if isinstance(key_or_list, list):
            if direction is not None:
                raise ValueError('direction can not be set separately '
                                 'if sorting by multiple fields.')
            for pair in key_or_list:
                if not isinstance(pair, (list, tuple)):
                    raise TypeError('key pair should be a list or tuple.')
                if not len(pair) == 2:
                    raise ValueError('Need to be (key, direction) pair')
                if not isinstance(pair[0], str):
                    raise TypeError('first item in each key pair must '
                                    'be a string')
                if not isinstance(pair[1], int) or not abs(pair[1]) == 1:
                    raise TypeError('bad sort specification.')

            sort_specifier = key_or_list

        elif isinstance(key_or_list, str):
            if direction is not None:
                if not isinstance(direction, int) or not abs(direction) == 1:
                    raise TypeError('bad sort specification.')
            else:
                # default ASCENDING
                direction = 1

            sort_specifier = [(key_or_list, direction)]

        else:
            raise ValueError('Wrong input, pass a field name and a direction,'
                             ' or pass a list of (key, direction) pairs.')

        # sorting

        _cursordat = self.cursordat

        total = len(_cursordat)
        pre_sect_stack = list()
        for pair in sort_specifier:

            is_reverse = bool(1-pair[1])
            value_stack = list()
            for index, data in enumerate(_cursordat):

                # get field value

                not_found = None
                for key in pair[0].split('.'):
                    not_found = True

                    if isinstance(data, dict) and key in data:
                        data = copy.deepcopy(data[key])
                        not_found = False

                    elif isinstance(data, list):
                        if not is_reverse and len(data) == 1:
                            # MongoDB treat [{data}] as {data}
                            # when finding fields
                            if isinstance(data[0], dict) and key in data[0]:
                                data = copy.deepcopy(data[0][key])
                                not_found = False

                        elif is_reverse:
                            # MongoDB will keep finding field in reverse mode
                            for _d in data:
                                if isinstance(_d, dict) and key in _d:
                                    data = copy.deepcopy(_d[key])
                                    not_found = False
                                    break

                    if not_found:
                        break

                # parsing data for sorting

                if not_found:
                    # treat no match as None
                    data = None

                value = self._order(data, is_reverse)

                # read previous section
                pre_sect = pre_sect_stack[index] if pre_sect_stack else 0
                # inverse if in reverse mode
                # for keeping order as ASCENDING after sort
                pre_sect = (total - pre_sect) if is_reverse else pre_sect
                _ind = (total - index) if is_reverse else index

                value_stack.append((pre_sect, value, _ind))

            # sorting cursor data

            value_stack.sort(reverse=is_reverse)

            ordereddat = list()
            sect_stack = list()
            sect_id = -1
            last_dat = None
            for dat in value_stack:
                # restore if in reverse mode
                _ind = (total - dat[-1]) if is_reverse else dat[-1]
                ordereddat.append(_cursordat[_ind])

                # define section
                # maintain the sorting result in next level sorting
                if not dat[1] == last_dat:
                    sect_id += 1
                sect_stack.append(sect_id)
                last_dat = dat[1]

            # save result for next level sorting
            _cursordat = ordereddat
            pre_sect_stack = sect_stack

        # done

        self.cursordat = _cursordat

        return self

    def hasNext(self):
        """
        Returns True if the cursor has a next position, False if not
        :return:
        """
        cursor_pos = self.cursorpos + 1

        try:
            self.cursordat[cursor_pos]
            return True
        except IndexError:
            return False

    def next(self):
        """
        Returns the next record
        :return:
        """
        self.cursorpos += 1
        return self.cursordat[self.cursorpos]

    @property
    def count(self):
        """
        Returns the number of records in the current cursor
        :return: number of records
        """
        return len(self.cursordat)

    def first(self):
        return self.cursordat[0] if len(self.cursordat) else None

    def last(self):
        return self.cursordat[:-1] if len(self.cursordat) else None


def query(data:list, filters:dict) -> List[dict]:
    return DictQuery(data).execute(filters) if filters and data else data
