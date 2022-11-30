# -----------------------------
# -- Angola --
# -----------------------------

import re
from slugify import slugify
from . import lib

# === AQL Functions
# -----------------------------------------------------------------------------

AQL_FILTER_LOGIC = {
    "$AND": " AND ",
    "$OR": " OR ",
    "$NOT": " NOT ",
    "$NOR": " NOR "
}

# AQL UTILITIES
AQL_FILTER_OPERATORS = {
    "$EQ": "==",  # equal
    "$NE": "!=",  # not equal
    "$GT": ">",  # greater than
    "$GTE": ">=",  # greater than or equal
    "$LT": "<",  # lesser than
    "$LTE": "<=",  # lesser than or equal
    "$IN": "IN",  # left hand in right hand array -> field.value IN [values]
    # left hand not in right hand array -> field.value NOT IN [values]
    "$XIN": "NOT IN",
    # right hand in left hand array -> values IN [field.value]
    "$INCLUDES": "IN",
    # right hand not in left hand array -> values NOT IN [field.value]
    "$XINCLUDES": "NOT IN",
    "$LIKE": "LIKE",  # search
    "$XLIKE": "NOT LIKE"  # ,

}
# reverse operator, where the right hand will point to left hand
# ie: cities:$includes:'charlotte' -> 'charlotte' IN cities
_rev_ops_order = ['$INCLUDES', '$XINCLUDES']


# -----------------------------------------------------------------------------
# === MACROS ------------------------------------------------------------------

def _re_match(pattern, value) -> re:
    return re.match(pattern, value, flags=re.IGNORECASE)


def _macro_currdate(re_match:re):
    """
    This macros eval the @@CURRENDATE in the query
    
    :Params:
        :re_match: regexp match the 

    Regex: 

    Example:
        {
            "_created_at:$gt": "@@CURRDATE() -5days"
        }

    Format: [@@CURRDATE($format) $shifter]
    Regex: ^\@\@CURRDATE\((.*)\)\s*(.*)$

        match[1] = format
        match[2] = shifter
    """
    dt_format = re_match[1] or "YYYY-MM-DD"
    shifter = re_match[2]
    now = lib.get_datetime()
    if shifter:
        now = lib.arrow_date_shifter(now, shifter)
    return now.format(dt_format )


MACROS_DEFS = [
    {
        # '@@CURRDATE(format=YYYY-MM-DD) shifter=+3Days 4Weeks'
        "name": "CURRDATE",
        "pattern": "^\@\@CURRDATE\((.*)\)\s*(.*)$",
        "func": _macro_currdate
    }
]


def eval_macros(value):
    for item in MACROS_DEFS:
        if isinstance(value, str) and (m := _re_match(item.get("pattern"), value)):
            return item.get("func")(m)
        elif isinstance(value, list):
            vs = []
            for v in value:
                if m := _re_match(item.get("pattern"), v):
                    vs.append(item.get("func")(m))
                else:
                    vs.append(v)
            return vs
    return value

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------


def aql_sort_builder(sorts: list, propkey: str) -> str:
    """
    Create a SORT clause

    Params
        sorts: list
            ["name:desc", "id:asc", "some.deep.path:desc"]
            alternative to list, it can be string
                sorts: "name:desc"
                sorts: "name" // will be ASC by default
        propkey:str
            the property key from the parent query
    Returns
        str
    """
    if not sorts:
        return ""

    # you can pass it as string
    # sorts: "name"
    if isinstance(sorts, str):
        sorts = [sorts]
    # make compatible with previous implementations.
    # sorts must now be a list, not dict.
    elif isinstance(sorts, dict):
        sorts = ["%s:%s" % (k, v) for k, v in sorts.items()]

    aql = ["%s.%s %s" % (propkey, s.split(":")[0], s.split(
        ":")[1] if len(s.split(":")) > 1 else "ASC") for s in sorts]
    return " SORT " + ", ".join(aql) + " "


def xql_collects_builder(collects: list, propkey: str) -> str:
    if not collects:
        return ""
    # TODO
    return ""


def _parse_filter_row(k, value, propkey):
    operator = "$EQ"  # default operator
    # extract the key and the operator
    # ie -> "name:$eq" or "city:$in"
    # link#, especially in join: "'name': '#parent.key'"

    if ":" in k:
        k, operator = k.split(":", 2)
        operator = operator.upper()

    # literal values starts with `#`
    # it indicates the value should not be converted, but rather return as is without `#`
    # ie:
    # - {k: "#parent.key"} -> k == parent.key
    # - {k: '#@params_value'} -> k == @params_value
    #
    dlit = isinstance(value, str) and value.startswith("#")

    # gen a unique number to make sure values generated are unique
    num_ = lib.gen_number(6)
    ukey = slugify("%s_%s" % (k, num_), separator="_")
    stmt = ""
    params = {}
    value = eval_macros(value=value)
    if dlit:
        value = value.replace("#", "")
        if operator in _rev_ops_order:  # reverse order
            stmt = " {value} {operator} {propkey}.{key}"
        else:
            stmt = " {propkey}.{key} {operator} {value}"
    else:
        params = {
            ukey: value
        }
        if operator in _rev_ops_order:  # reverse order
            stmt = " @{ukey} {operator} {propkey}.{key}"
        else:
            stmt = " {propkey}.{key} {operator} @{ukey}"

    aql = stmt.format(
        value=value,
        propkey=propkey,
        key=k,
        operator=AQL_FILTER_OPERATORS[operator],
        ukey=ukey)

    return aql, params


def aql_filter_builder(filters: dict, propkey: str) -> tuple:
    """
    Create a FILTER clause

    Params:
        filter: dict
            {
                'name': 'something',
                'age:$gt': 18,
                'cities:$in': ['charlotte', 'Concord'],
                '$or': [{
                       "cities:$in": [],
                       "_perms.read:$in":[] 
                 }]
                ]
            }
        propkey:str
            the property key from the parent query

    Returns
        tuple(aql:str, params:dict)

    """
    params = {}
    aql = ""
    for k in filters:

        if k.startswith("$"):
            k_ = k.upper()
            # operation
            if k_ in AQL_FILTER_LOGIC.keys() and isinstance(filters[k], (dict, list)):
                fk = filters[k]
                if isinstance(fk, dict):
                    fk = [fk]
                for k0 in fk:
                    tmp_aql = []
                    for k2 in k0:
                        _aql, _params = _parse_filter_row(k2, k0[k2], propkey)
                        tmp_aql.append(_aql)
                        params.update(_params)
                    aql += "FILTER (%s)\n" % AQL_FILTER_LOGIC[k_].join(tmp_aql)
            else:
                raise Exception("Invalid logic: %s" % k)
        else:
            _aql, _params = _parse_filter_row(k, filters[k], propkey)
            aql += "FILTER (%s)\n" % _aql
            params.update(_params)
        # value = filters[k]
        # operator = "$EQ"  # default operator

        # # extract the key and the operator
        # # ie -> "name:$eq" or "city:$in"
        # if ":" in k:
        #     k, operator = k.split(":", 2)
        #     operator = operator.upper()

        # # gen a unique number to make sure values generated are unique
        # num_ = lib.gen_number(6)
        # ukey = "%s_%s" % (k, num_)
        # aql += " FILTER {propkey}.{key} {operator} @{ukey} \n".format(
        #     propkey=propkey,
        #     key=k,
        #     operator=AQL_FILTER_OPERATORS[operator],
        #     ukey=ukey)
        # params[ukey] = value
    return aql, params


def prepare_xql(xql: dict) -> dict:
    _defaults = {
        "FROM": None,
        "ON": None,
        "AS": "doc__",
        "FILTER": {},
        "SORT": None,
        "SKIP": None,
        "COUNT_AS": None,
        "TAKE": 10,
        "PAGE": 1,
        "JOIN": [],
        "RETURN": "doc__",
        "RETURN_WITH": None,
        **xql
    }
    return {k.upper(): v for k, v in _defaults.items()}


def xql_take_skip_page(xql: dict, max_limit=100) -> tuple:
    """
    Returns:
        type: tuple(TAKE:int, SKIP:int, PAGE:1)
            - TAKE: limit/per_page
            - SKIP: offset
            - PAGE: page #
    """
    xql = prepare_xql(xql)
    SKIP = xql.get("SKIP")
    TAKE = xql.get("TAKE") or 10
    PAGE = xql.get("PAGE") or 1

    if SKIP is None:
        page = PAGE or 1
        per_page = TAKE
        if per_page > max_limit:
            per_page = max_limit
        SKIP = lib.calc_pagination_offset(page=page, per_page=per_page)
        TAKE = per_page
    if TAKE > max_limit:
        TAKE = max_limit

    return TAKE, SKIP, PAGE


class XQLDEFINITION:
    """
    XQL Schema Definition:

        :param FROM: str = the collection name
        :param AS: str = alias
        :param FILTER: dict = filters
        :param SORT: list/str = sort 
        :param SKIP: int = the offset of the limit, default=0
        :param TAKE: int = the limit of result, default=10
        :param PAGE: int = help calculate the skip by using a page number. 
        :param JOIN: list[XQL]
        :param ON: str = when using join, it links the primary _key 
        :param COUNT_AS: str =  To count all the document, and return the value. Alias to `COLLECT WITH COUNT INTO`
        :param RETURN: str = string representation
        :param MERGE: str = on JOIN, to merge the data.
            ie: MERGE: "{__profile: profile}" 
            Can be done manually with RETURN MERGE(doc, {data})

    """
    FROM: str = None
    AS: str = None
    FILTER: dict = {}
    SORT: list = []
    SKIP: int = 0
    TAKE: int = 10
    PAGE: int = 1
    JOIN: list = []
    ON: str = None
    COUNT_AS: str = None
    RETURN: str = None
    MERGE: str = None


def xql_to_aql(xql: dict, vars: dict = {}, max_limit=100, parser=None):
    """
    XQL:=
    Xtensible Query Language to query data in ArangoDB 

    Params:
        xql: 
            type: dict = the XQL schema
        max_limit:
            type: int = a max number
        parser:
            type: function
        vars:
            type: dict - Variables for FILTER and FILTER_WHEN

    Returns:
        tuple(AQL:string, BIND_VARS:dict)

    ===
    XQL Schema Definition:
        FROM: str = the collection name
        AS: str = alias
        FILTER: dict = filters
        SORT: list/str = sort 
        SKIP: int = the offset of the limit, default=0
        TAKE: int = the limit of result, default=10
        PAGE: int = help calculate the skip by using a page number. 
        JOIN: list[XQL]
        ON: str = when using join, it links the primary _key 
        COUNT_AS: str =  To count all the document, and return the value. Alias to `COLLECT WITH COUNT INTO`
        RETURN: str = string representation
        MERGE: str = on JOIN, to merge the data.
            ie: MERGE: "{__profile: profile}" 
            Can be done manually with RETURN MERGE(doc, {data})


        # TODO
        - WHEN: ? = a conditional to evaluate before running
        - FILTER_WHEN: add additional filters when a condition is true

    === 
    schema example:
        FROM: collection
        AS: alias1
        FILTER:
            x:y
            "z:$gt": 5
        SORT: name:desc
        JOIN:
            FROM: collection2
            AS: c2
            FILTER:
                d: "#alias1.d"
            TAKE: 5
            PAGE: 2
            RETURN: c2
        TAKE: 10
        SKIP: 2
        RETURN 
            d
            c2


        === code example
        q = {
            "FROM": "job_posts",
            "AS": "post",
            "FILTER": {
                "a": "b",
                "c:$gt": 5
            },
            "SORT": ["id:desc"],
            "TAKE": 10,
            "SKIP": 47,
            "JOIN": [
                {
                    "AS": "app",
                    "FROM": "application",
                    "FILTER": {
                        "a": "b",
                        "c": "d",
                        "d": "#job.v_d"
                    },
                    "JOIN": [        {
                        "AS": "J_loco",
                        "FROM": "bam",
                        "FILTER": {
                            "a": "b",
                            "c": "d",
                            "d": "#app.v_d"
                        }
                    }]
                },
                {
                    "FROM": "loco",
                    "AS": "bam",
                    "FILTER": {
                        "a": "b",
                        "c": "d",
                        "d": "#app.v_d"
                    }
                }
            ],
            "RETURN": "MERGE(post, {__account: loco})"
    """

    xql = prepare_xql(xql)

    if not xql.get("AS"):
        xql["AS"] = "doc__"

    ALIAS = xql.get("AS") or "doc__"

    if parser:
        xql = parser(xql)

    COLLECTION = xql.get("FROM")
    FILTERS = xql.get("FILTER") or {}
    SORTS = xql.get("SORT")
    SKIP = xql.get("SKIP")
    TAKE = xql.get("TAKE") or 10
    PAGE = xql.get("PAGE") or 1
    JOINS = xql.get("JOIN") or []
    COUNT_AS = xql.get("COUNT_AS")
    COLLECTS = xql.get("COLLECT") or []
    RETURN = xql.get("RETURN") or ALIAS

    # work with take/skip
    if SKIP is None:
        page = PAGE or 1
        per_page = TAKE
        if per_page > max_limit:
            per_page = max_limit
        SKIP = lib.calc_pagination_offset(page=page, per_page=per_page)
        TAKE = per_page
    if TAKE > max_limit:
        TAKE = max_limit

    # unique num to give each field to prevent name collision
    num_ = lib.gen_number(6)
    aql_filter, filter_vars = aql_filter_builder(FILTERS, propkey=ALIAS)
    aql_sorting = aql_sort_builder(SORTS, propkey=ALIAS)
    aql_collects = xql_collects_builder(COLLECTS, propkey=ALIAS)
    if COUNT_AS:
        aql_collects += " COLLECT WITH COUNT INTO %s " % COUNT_AS

    bind_vars = {}

    # SUBQUERY/JOINS
    subquery = ""
    for xql2 in JOINS:
        xql2 = prepare_xql(xql2)
        X = xql_to_aql(xql=xql2, parser=parser, max_limit=max_limit)
        subquery += "\nLET %s = (%s) \n" % (xql2.get("AS"), X[0])
        bind_vars.update(X[1])

    # Query
    query = "FOR {alias} IN @@collection_{num_} ".format(
        alias=ALIAS, num_=num_)
    query += aql_filter
    query += subquery
    query += aql_collects
    query += " LIMIT @skip_%s, @limit_%s " % (num_, num_)
    query += aql_sorting
    query += "RETURN UNSET_RECURSIVE(%s, ['_id', '_rev', '_old_rev'])" % RETURN

    bind_vars.update({
        **filter_vars,
        "skip_%s" % num_: SKIP,
        "limit_%s" % num_: TAKE,
        "@collection_%s" % num_: COLLECTION
    })

    return query, bind_vars


def xql_extract_collections(xql: dict) -> list:
    """
    Extract all the collection names. 
    This can help with testing collection name

    Args:
        xql: dict

    Returns: 
        dict
    """
    xql = prepare_xql(xql)
    JOINS = xql.get("JOIN") or []
    collections = []
    for xql2 in JOINS:
        collections.extend(xql_extract_collections(xql2))
    collections.append(xql.get("FROM"))
    return list(set(collections))


def aql_detect_modifier_operations(aql: str) -> bool:
    """
    Detect if an AQL has retricted modifier operators.
    Use if we expect AQL to Query and not modify entries

    Params:
      @aql:
          type:str

    Returns
      bool

    """
    operators = ["REMOVE", "UPDATE", "REPLACE", "INSERT", "UPSERT"]
    return len([r for r in aql.split() if r.upper() in operators]) > 0


def aql_get_filter_keys(filters: dict) -> list:
    """
    Return all keys that are used for the filters
    """
    keys = set()
    for k in filters:
        if k.startswith("$"):
            k_ = k.upper()
            # operation
            if k_ in AQL_FILTER_LOGIC.keys() and isinstance(filters[k], (dict, list)):
                fk = filters[k]
                if isinstance(fk, dict):
                    fk = [fk]
                for k0 in fk:
                    for k2 in k0:
                        if ":" in k2:
                            _ = k2.split(":", 2)
                            keys.add(_[0])
                        else:
                            keys.add(k2)
            else:
                raise Exception("Invalid logic: %s" % k)
        else:
            if ":" in k:
                _ = k.split(":", 2)
                keys.add(_[0])
            else:
                keys.add(k)
    return list(keys)

