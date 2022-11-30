#-----------------------------
# -- Angola --
#-----------------------------

import os
import re
import sys
import json
import ulid
import math
import uuid
import time
import arrow
import string
import random
import secrets
import hashlib
import datetime
from slugify import slugify
from jinja2 import Template
from functools import reduce
from operator import itemgetter
from typing import Iterator, Any


def collection_name_valid(name):
    """
    Valid a collection name 
    length: 2, 64
    pattern: lowercase, letters and numbers and underscore
    """
    pattern = re.compile(r"^[a-z][a-z0-9\_]{2,64}$")
    return bool(pattern.match(name)) 


def gen_key() -> str:
    """
    Returns ULID. 26 chars
    """
    return str(ulid.new()).lower()


def gen_uuid() -> str:
    """
    Return a UUID4 key. 32 chars
    """
    return ("%s" % uuid.uuid4()).replace("-", "")

def gen_name(length:int=8) -> str:
    """
    Generate a random name
    semi-pronounceable, semi-memorable
    """
    consonants = "bcdfghjklmnpqrstvwxyz"
    vowels = "aeiou"
    return "".join(random.choice((consonants, vowels)[i % 2]) for i in range(length))


def gen_number(length:int=4) -> int:
    """
    Generate random number
    """
    return ''.join(random.choice(string.digits) for _ in range(length))


def gen_random_password(length:int=20) -> str:
    """
    Generate a random password
    """
    return secrets.token_urlsafe(length)

def gen_dbname(str_len=8, num_len=4):
    """
    Generate a random database name of 12 chars
    """
    return gen_name(str_len) + gen_number(num_len)

# ====

def sanitize_custom_key(key:str) -> str:
    """
    To sanitize a custom key

    Returns:
        string
    """
    return slugify(key, separator="")

def sanitize_custom_name(name:str) ->str:
    """ Sanitize a custom name """
    return slugify(name, separator="_", max_length=64)
    

def make_scoped_name(scope:str, name:str) -> str:
    """
    Create a scoped name
    """
    name = sanitize_custom_name(name)
    return "%s--%s" % (scope.lower(), name)


def parse_scoped_name(scoped_name:str) -> tuple:
    """
    Parse scoped name to return the scope and name
    Returns:
        (scope, name)
        
    """
    sn = scoped_name.split("--", 1)
    return tuple(sn) if  len(sn) == 2 else (None, sn[0])


# === DATE + TIME 
def get_datetime() -> arrow.Arrow:
    """
    Generates the current UTC timestamp with Arrow date

    ISO FORMAT
    Date    2022-08-13
    Date and time in UTC : 2022-08-13T22:45:03+00:00

    Returns:
      Arrow UTC Now
    """
    return arrow.utcnow()


def arrow_date_shifter(dt: arrow.Arrow, stmt: str) -> arrow.Arrow:
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

def arrow_date_format(dt:arrow.Arrow, format:str='YYYY-MM-DD HH:mm:ss ZZ') -> str:
    return dt.format(format)


def get_timestamp() -> int:
    """
    Generates the current UTC timestamp with datetime
    Returns:
      int
    """
    return round(datetime.datetime.utcnow().timestamp())



# === JSON 

def _json_serialize(o):
    return timestamp_to_str(o)

def _json_deserialize(json_dict):
    for k, v in json_dict.items():
        if isinstance(v, str) and timestamp_valid(v):
            json_dict[k] = arrow.get(v)
    return json_dict

def timestamp_to_str(dt) -> str:
    if isinstance(dt, arrow.Arrow):
        return dt.for_json()
    elif isinstance(dt, (datetime.date, datetime.datetime)):
        return dt.isoformat()
    return dt


def timestamp_valid(dt_str) -> bool:
    try:
        datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except:
        return False
    return True



# ----------------------
# json_ext

class json_ext:
    """ 
    JSON Extension class to loads and dumps json
    """

    @classmethod
    def dumps(cls, data: dict) -> str:
        """ Serialize dict to a JSON formatted """
        return json.dumps(data, default=cls._serialize)

    @classmethod
    def loads(cls, data: str) -> dict:
        """ Deserialize a JSON string to dict """
        if not data:
            return None
        if isinstance(data, list):
            return [json.loads(v) if v else None for v in data]
        return json.loads(data, object_hook=cls._deserialize)

    @classmethod
    def _serialize(cls, o):
        return cls._timestamp_to_str(o)

    @classmethod
    def _deserialize(cls, json_dict):
        for k, v in json_dict.items():
            if isinstance(v, str) and cls._timestamp_valid(v):
                json_dict[k] = arrow.get(v)
        return json_dict

    @staticmethod
    def _timestamp_valid(dt_str) -> bool:
        try:
            datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            return False
        return True

    @staticmethod
    def _timestamp_to_str(dt) -> str:
        if isinstance(dt, arrow.Arrow):
            return dt.for_json()
        elif isinstance(dt, (datetime.date, datetime.datetime)):
            return dt.isoformat()
        return dt

# alias 
json_dumps = json_ext.dumps
json_loads = json_ext.loads



# === DICT extensions

def flatten_dict(_dict: dict, _str: str = '', reducer=None) -> dict:
    """
    To flatten a dict. Nested node will be separated by dot or separator
    It takes in consideration dict in list and flat them.
    Non dict stay as is

    Args:
        ddict:
        prefix:
    Returns:
        dict

    """
    sep = "."
    ret_dict = {}
    for k, v in _dict.items():
        if isinstance(v, dict):
            ret_dict.update(flatten_dict(v, _str=sep.join([_str, k]).strip(sep)))
        elif isinstance(v, list):
            _k =  ("%s.%s" % (_str, k)).strip(sep)
            ret_dict[_k] = [flatten_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            ret_dict[sep.join([_str, k]).strip(sep)] = v
    return ret_dict


def unflatten_dict(flatten_dict: dict) -> dict:
    """
    To un-flatten a flatten dict

    Args:
      flatten_dict: A flatten dict
    Returns:
      an unflatten dictionnary
    """
    output = {}
    for k, v in flatten_dict.items():
        path = k.split(".")
        if isinstance(v, list):
            v = [unflatten_dict(i2) if isinstance(i2, dict) else i2 for i2 in v]
        _set_nested(output, path, v)
    return output


def _get_nested_default(d, path):
    return reduce(lambda d, k: d.setdefault(k, {}), path, d)


def _set_nested(d, path, value):
    _get_nested_default(d, path[:-1])[path[-1]] = value


def dict_pick(ddict: dict, keys: list, check_keys=False) -> dict:
    """
    To pick and return specific keys from a flatten dict.

    Args:
      ddict: dict
      keys: A list of dot notation path to keep
      check_keys: bool - check if all keys exist

    Returns:
      a dict with the picked value

    Example
      keys: ["name", "location.city"]
      flatten_dict: { "name": "MM", "location.city": "Charlotte",
          "location.state": "NC", "age": 100}
      returns: {
        "name": "MM",
        "location": {
          "city": "Charlotte"
        }
      }
    """
    fd = flatten_dict(ddict)

    # check that all keys exist
    if check_keys:
        for k in keys:
            assert k in fd, "missing key '%s'" % k

    ufd = _dict_pick_merge_l2d([_dict_pick_lookup_dict(fd, k) for k in keys])
    return unflatten_dict(ufd)


def _dict_pick_merge_l2d(iter: list):
    """
    Flatten a looked up list of tuples into dict
    Returns dict
    """
    df = {}
    for u in iter:
        if isinstance(u, list):
            for u2 in u:
                df[u2[0]] = u2[1]
    return df


def _dict_pick_lookup_dict(fd, k):
    """
    To lookup a key in a flatten dict 
    If the key is not found directly, it will start from the parent dot

    Returns list of tuples
    """
    if k in fd:
        return [(k, fd[k])]
    p = []
    for dk, dv in fd.items():
        if dk.startswith("%s." % k):
            p.append((dk, dv))
    return p


def dict_find_replace(ddict: dict, kv_repl: dict, is_flatten=False):
    """
    Find/Replace a KV dict in a dict

    Args:
      - ddict
      - kv_repl
      - is_flatten

    Returns
      dict
    """

    fd = ddict
    for k, v in fd.items():
        if isinstance(v, str) and v in kv_repl:
            fd[k] = kv_repl[v]
        elif isinstance(v, list):
            for l, e in enumerate(v):
                if isinstance(fd[k][l], str) and fd[k][l] in kv_repl:
                    fd[k][l] = kv_repl[fd[k][l]]
                elif isinstance(fd[k][l], dict):
                    fd[k][l] = dict_find_replace(fd[k][l], kv_repl)
        elif isinstance(v, dict):
            fd[k] = dict_find_replace(v, kv_repl)
    return fd


def dict_set(my_dict, key_string, value):
    """
    dict_set
    Mutable
    """
    here = my_dict
    keys = key_string.split(".")
    for key in keys[:-1]:
        here = here.setdefault(key, {})
    here[keys[-1]] = value


def dict_get(obj, path, default=None):
    """
    Get a value via dot notaion

    Args:
        @obj: Dict
        @attr: String - dot notation path
            object-path: key.value.path
            object-with-array-index: key.0.path.value
    Returns:
        mixed
    """
    def _getattr(obj, path):
        try:
            if isinstance(obj, list) and path.isdigit():
                return obj[int(path)]
            return obj.get(path, default)
        except:
            return default
    return reduce(_getattr, [obj] + path.split('.'))

def dict_pop(obj:dict, path:str) -> Any:
    """
    * Mutates #obj

    To pop a property from a dict dotnotation

    Args:
        obj:dict - This object will be mutated
        path:str - the dot notation path to update
        value:Any - value to update with

    Returns:
        Any - The value that was removed
    """

    here = obj 
    keys = path.split(".")

    for key in keys[:-1]:
        here = here.setdefault(key, {})
    if isinstance(here, dict):
        return here.pop(keys[-1])
    else:
        val = here[keys[-1]]
        del here[keys[-1]]
        return val



def dict_merge(*dicts) -> dict:                                                            
    """         
    Deeply merge an arbitrary number of dicts                                                                    
    Args:
        *dicts
    Return:
        dict

    Example
        dict_merge(dict1, dict2, dict3, dictN)
    """                                                                             
    updated = {}                                                                    
    # grab all keys                                                                 
    keys = set()                                                                    
    for d in dicts:                                                                 
        keys = keys.union(set(d))                                                   

    for key in keys:                                                                
        values = [d[key] for d in dicts if key in d]                                                                
        maps = [value for value in values if isinstance(value, dict)]            
        if maps:                                                                    
            updated[key] = dict_merge(*maps)                                       
        else:                                                                                                      
            updated[key] = values[-1]                                               
    return updated 

def chunk_list (lst:list, n:int):
    """
    Yield successive n-sized chunks from lst.
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def dict_upper_keys(obj) -> dict:
    """
    Change all the keys to uppercase in dict
    Args:
        obj: dict
    Returns
        dict

    """
    return { k.upper(): v for k, v in obj }

def list_sorted_dict(l:list, key:str) -> list:
    """
    To order a list of dict, by the value in the dict

    list_sorted_dict(list, "name")
    """
    return sorted(l, key=itemgetter(key))

#===

def hash_string(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def calc_pagination_offset(page: int, per_page: int) -> int:
    """
    Calculate a pagination offset. 
    To use with LIMIT offset, per_page

    Args:
        - page:int - the current page
        - per_page:int - items per page
    Returns: int 
    """
    return 0 if page < 1 else (page - 1) * per_page


def gen_pagination(total_count: int, count: int, page: int, per_page: int) -> dict:
    """
    Create pagination data based on some basic info

    Args:
        - total_count:int - The total items
        - count:int - the current count for the subset
        - page:int - the current page
        - per_page:int - total items per page

    Returns: dict
        - page:int - The current page
        - per_page:int - total items per page
        - total_count:int - total items
        - page_count:int - the current count for the page
        - page_showing_start:int|None - data start, ie: showing *1 to 10
        - page_showing_end:int|None - data end, ie: showing 1 to *10
        - total_pages:int - total pages
        - has_prev:bool - If it has prev page
        - prev_page:int|None - the prev page # or None
        - has_next:bool - If it has next page
        - next_page:int|None - the next page # or None

    """
    per_page = int(round(per_page))
    if per_page < 1:
        per_page = 10
    total_pages = math.ceil(total_count / per_page)
    page = int(round(page))
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    has_prev = page > 1 and page <= total_pages
    has_next = page < total_pages
    _offset = calc_pagination_offset(page=page, per_page=per_page)
    page_showing_start =  _offset + 1
    page_showing_end = _offset + count
    if total_pages == 0:
        page_showing_start = 0
        page_showing_end = 0
        
    return {
        "page": page,
        "per_page": per_page,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_prev": has_prev,
        "prev_page": page - 1 if has_prev else None,
        "has_next": has_next,
        "next_page": page + 1 if has_next else None,
        "last_page": total_pages,
        "page_count": count,
        "page_showing_start": page_showing_start,
        "page_showing_end": page_showing_end
    }


def render_template(source: str, data={}, is_data_flatten=False) -> str:
    """
    Render Template string with interpolation
    """
    _data = data.copy()
    if _data and is_data_flatten:
        _data = unflatten_dict(_data)
    return Template(source).render(**_data)

def parse_str_template(source: str, data={}):
    """Parse template string with"""
    return Template(source).render(**data)


def parse_dict_template(source: dict, data: dict = {}):
    for k in source:
        if isinstance(source[k], list):
            source[k] = [parse_str_template(i, data) for i in source[k]]
        elif isinstance(source[k], dict):
            source[k] = parse_dict_template(source[k], data)
        else:
            source[k] = parse_str_template(source[k], data)
    return source


def write_template_file(file, data={}):
    """Parse template file with data"""
    with open(file, "r+") as f:
        content = parse_str_template(f.read(), data)
        f.truncate(0)
        f.seek(0)
        f.write(content)
