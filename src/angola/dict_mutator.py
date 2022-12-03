#-----------------------------
# -- Angola --
#-----------------------------

import re
import copy
import arrow
import uuid
from . import lib

# ----

def _j2_currdate(format_="YYYY-MM-DD", shifter=None):
    dt = _get_datetime()
    if shifter:
        dt = _arrow_date_shifter(dt=dt, stmt=shifter)
    if format_.upper() == "ISODATE":
        return dt
    return lib.arrow_date_format(dt, format_)

# ----

# Operators that work with list
LISTTYPES_OPERATORS = ["xadd", "xadd_many", "xrem", "xrem_many", "xpush", "xpush_many", "xpushl", "xpushl_many"]

# _NMutDict: A dict thats aggregates data to be mutated in a nested context
class _NMutDict(dict): pass

# _NMutList: A list of data to be mutatated in a nested context
class _NMutList(list): pass

# _FlattenDictType - Data Type flatten_dict
class _FlattenDictType(dict): pass

# To unset a value from being updated
class _UnOperableValue(object): pass


def mutate(mutations: dict, init_data: dict = {}, immuts:list=[], custom_ops:dict={}):
    """
    mutate

    Args:
        mutations:dict - data contains operators to update
        init_data:dict - initial data 
        immuts: list - list of keys to not mutate
        custom_ops: dict - dict of custom operations

    Returns:
        tuple(updated_data:dict, oplog)

    """
    _muts = lib.flatten_dict(mutations)
    _inits = lib.flatten_dict(init_data)
    muts = {}
    _restructed = {}

    for k, v in _muts.items():
        # since data is flat, let's restructure some data so they can be properly mutated
        xl = list(filter(lambda v: v, re.split("(\:\$\w+)(?:\.)?", k)))
        if len(xl) > 2:
            _op = xl[1].replace(":$", "")
            if _op in LISTTYPES_OPERATORS:
                _pathkey = "%s:$%s" % (xl[0], _op)
                if _pathkey not in _restructed:
                    _restructed[_pathkey] = _NMutDict()
                _jpath = ".".join(xl[2:]).replace(".:$", ":$")
                _restructed[_pathkey][_jpath] = v
            else:
                muts[k] = _NMutList([_NMutDict(vv) if isinstance(vv, dict) else vv for vv in v]) if isinstance(v, list) else v
        else:
            # by default, data will be a :$set. This will allow inner updat
            k = "%s:$set" % k if ":$" not in k else k
            muts[k] = _NMutList([_NMutDict(vv) if isinstance(vv, dict) else vv for vv in v]) if isinstance(v, list) else v

    muts.update(_restructed)
    d, _ = _mutate(mutations=muts, init_data=_inits, immuts=immuts, custom_ops=custom_ops)
    return lib.unflatten_dict(d), _


def _mutate(mutations:_FlattenDictType, init_data:_FlattenDictType={}, immuts:list=[], custom_ops:dict={}):
    """
    Mutation operations

    Args:
        mutations:dict - data contains operators to update
        init_data:dict - initial data 
        immuts: list - list of keys to not mutate
        custom_ops: dict - dict of custom operations

    Returns:
        tuple(updated_data:_FlattenDictType, oplog)

    Operators:
        $incr - to increase an INT value
        $decr - to decrease an INT value
        $unset - To remove a property
        $currdate - gen the current datetime. Can manipulate time
        $template - Evalute the string as template
        $uuid4 - gen a UUID4 string, without the dashes
        $xadd - add item if doesn't exist
        $xadd_many - add many items in the list if not already in the list
        $xrem - remove item
        $xrem_many - remove many items in a list
        $xpush - push item on the right
        $xpush_many - push many items in a list on the right
        $xpushl - push item on the left
        $xpushl_many - push many items in a list on the left
        $xpop - pop an item from a list on the right 
        $xpopl - pop an item from a list on the left
        $xlen - calculate the length of an object
        
    Example
        {
           "key:$incr": True|1,
           "key:$decr": True|1,
           "some.key:$unset": True,
           "some.list:$xadd": Any,
           "some.list:$xadd_many": [Any, Any, Any, ...],
           "some.list:$xrem": Any,
           "some.list:$xrem_many": [Any, Any, Any, ...],     
           "some.list:$xpush": Any,
           "some.list:$xpush_many": [Any, Any, Any, ...],   
           "some.list:$xpushl": Any,
           "some.list:$xpushl_many": [Any, Any, Any, ...],    
           "some.list:$xpop": True,
           "some.list:$xpopl: False,
           "some.value:$xlen": "some.data.path",
           "some.datetimefield:$currdate": True,             
           "some.datetimefield:$currdate": "+1Day +2Hours 5Minutes",
           "some.key:$template": "Hello {{ name }}!",
           "some.random.id:$uuid4": True             
        }

    Custom operations
        Extends the dict mutator with custom operations 

        It's K/V pair with key being the name of the operation and value a callable with
            def name(data, path, value)
        

        ie:
            def _new_uuid4(data, path, value):
                return str(uuid.uuid4()).replace("-")

            custom_ops = { 
                "new_uuid4": _new_uuid4
            }

            ops = {
                "new_uid:$new_uuid4": True
            }    
    """
    data = copy.deepcopy(init_data)
    oplog = {}
    postproc = {}

    # disabled immuts
    immuts = []
    
    for path, value in mutations.items():

        # -- skip
        if immuts and path in immuts:
            continue 

        if ":" in path:
            # -- skip
            if ":$" not in path:
                continue
            
            # _NMutDict
            if isinstance(value, _NMutDict):
                value = _mutate(value)[0]
            
            # _NMutList
            if isinstance(value, _NMutList):
                value = [ _mutate(vv)[0] if isinstance(vv, dict) else vv for vv in value]

            oppath = path
            oplog_path = path
            path, op = path.split(":$")

            # -- skip
            if immuts and path in immuts:
                continue 
            
            # post-process data. To be parsed later
            if op in ["template", "xlen"]:
                postproc[oppath] = value 
                continue 


            # $set. literal assigment, leave as is 
            if op == "set":
                pass

            # $incr
            elif op == "incr":
                value = _get_int_data(data, path) + \
                    (value if isinstance(value, int) else 1)
                oplog[oplog_path] = value

            # $decr
            elif op == "decr":
                _ = (value if isinstance(value, int) else 1) * -1
                value = _get_int_data(data, path) + _
                oplog[oplog_path] = value

            # $unset
            elif op == "unset":
                v = _pop(data, path)
                oplog[oplog_path] = v
                value = _UnOperableValue()

            # $currdate
            elif op == "currdate":
                dt = _get_datetime()
                if value is True:
                    value = dt
                else:
                    try:
                        if isinstance(value, str):
                            value = _arrow_date_shifter(dt=dt, stmt=value)
                        else:
                            value = _UnOperableValue()
                    except:
                        value = _UnOperableValue()

            # $uuid4
            elif op == "uuid4":
                value = str(uuid.uuid4())


            # LIST operators

            elif op in (
                "xadd", "xadd_many",
                "xrem", "xrem_many",
                "xpush", "xpush_many",
                "xpushl", "xpushl_many"
            ):
                values = _values_to_mlist(value, many=op.endswith("_many"))
                v = _get_list_data(data, path)

                # $xadd|$xadd_many
                if op.startswith("xadd"):
                    for val in values:
                        if val not in v:
                            v.append(val)
                    value = v

                # $xrem|$xrem_many
                elif op.startswith("xrem"):
                    _removed = False
                    for val in values:
                        if val in v:
                            _removed = True
                            v.remove(val)
                    value = v
                    if not _removed:
                        value = _UnOperableValue()

                # $xpush|$xpush_many
                elif op in ("xpush", "xpush_many"):
                    v.extend(values)
                    value = v

                # $xpushl|$xpushl_many
                elif op in ("xpushl", "xpushl_many"):
                    v2 = list(values)
                    v2.extend(v)
                    value = v2

            # $xpop
            elif op == "xpop":
                v = _get_list_data(data, path)
                if len(v):
                    value = v[:-1]
                    oplog[oplog_path] = v[-1]

            # $xpopl
            elif op == "xpopl":
                v = _get_list_data(data, path)
                if len(v):
                    value = v[1:]
                    oplog[oplog_path] = v[0]

            # $$custom_ops, add to post process
            elif op in custom_ops:
                postproc[oppath] = value 
                continue 

            # _UnOperableValue
            else:
                value = _UnOperableValue()

        if not isinstance(value, _UnOperableValue):
            data[path] = value

    # Post process
    if postproc:
        for path, value in postproc.items():            
            try:
                if ":" in path:
                    # -- skip
                    if ":$" not in path:
                        continue

                    path, op = path.split(":$")

                    # -- skip
                    if path in immuts:
                        continue 

                    # $template
                    if op == "template": 
                        _tpl_data =  {
                            **data,
                            "CURRDATE": _j2_currdate
                        }              
                        data[path] = lib.render_template(source=value, data=_tpl_data, is_data_flatten=True)
                    
                    # $xlen
                    elif op == "xlen" and value:
                        v = _get(data, value)
                        data[path] = len(v) if v else 0

                    # custom ops
                    elif op in custom_ops:
                        data[path] = custom_ops[op](data, path, value)

            except:
                pass


    return data, oplog


def _get(data:dict, path):
    """
    _get: Alias to get data from a path
    """
    return data.get(path)

def _set(data:dict, path, value):
    """
    _set: Alias to set value in data
    """
    data[path] = value
    return data

def _pop(data, path):
    """
    _pop: Alias to remove object from data
    """
    if path in data:
        return data.pop(path)
    return None 

def _get_int_data(data: dict, path: str) -> int:
    """
    _get_int_data: Returns INT for number type operations
    """
    v = _get(data, path)
    if v is None:
        v = 0
    if not isinstance(v, int):
        raise TypeError("Invalid data type for '%s'. Must be 'int' " % path)
    return v

def _get_list_data(data: dict, path: str) -> list:
    """
    _get_list_data: Returns a data LIST, for list types operations
    """
    v = _get(data, path)
    if v is None:
        return []
    if not isinstance(v, list):
        raise TypeError("Invalid data type for '%s'. Must be 'list' " % path)
    return v

def _values_to_mlist(value, many=False) -> list:
    """
    _values_to_mlist: Convert data multiple list items
    """
    return [value] if many is False else value if isinstance(value, (list, tuple)) else [value]

def _arrow_date_shifter(dt: arrow.Arrow, stmt: str) -> arrow.Arrow:
    """
    To shift the Arrow date to future or past

    Args:
        dt:arrow.Arrow - 
        stmt:str - 
    Returns:
        arrow.Arrow


    Valid shift:
        YEARS, MONTHS, DAYS, HOURS, MINUTES, SECONDS, WEEKS

    Format: [[+/-][$NUMBER][$SHIFT][SPACE]... ]
        +1Days
        -3Hours 6Minutes
        +1Days 2Hours 3Minutes
        1Year 2Month +3Days 5Hours -6Minutes 3Seconds 5weeks
    """
    shifts = ["years", "months", "days",
              "hours", "minutes", "seconds", "weeks"]

    t = [t for t in stmt.split(" ") if t.strip(" ")]
    t2 = [re.findall(r'((?:\+|\-)?(?:\d+))?(\w+)?', s)[0] for s in t if s]
    t2 = [(t[1].lower(), int(t[0])) for t in t2 if t[0] and t[1]]
    kw = {}
    for k, v in t2:
        if k in shifts or "%ss" % k in shifts:
            k = k if k.endswith("s") else "%ss" % k
            kw[k] = v
    if kw:
        dt = dt.shift(**kw)
        return dt

    return dt

def _get_datetime() -> arrow.Arrow:
    """
    Generates the current UTC datetime with Arrow date

    ISO FORMAT
    Date    2022-08-13
    Date and time in UTC : 2022-08-13T22:45:03+00:00

    Returns:
      Arrow UTC Now
    """
    return arrow.utcnow()

