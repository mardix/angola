import pytest
from kongodb import lib
import arrow 


def test_gen_id():
    key = lib.gen_id()
    assert len(key) == 26

def test_get_timestamp():
    assert isinstance(lib.get_timestamp(), arrow.Arrow)

def test_dict_get():
    data = {
        "key": "Yo",
        "key2": {
            "key3": "Hello",
            "key4": {
                "location": "NC"
            }
        }
    }
    assert lib.dict_get(data, "key") == "Yo"
    assert lib.dict_get(data, "key2.key3") == "Hello"
    assert lib.dict_get(data, "key2.key4.location") == "NC"


def test_dict_set():
    data = {
        "key": "value"
    }
    lib.dict_set(data, "key", "Loso")
    lib.dict_set(data, "key2.key3", "Hello")
    lib.dict_set(data, "key2.key4", {"location": "NC"})

    assert data["key"] == "Loso"
    assert data["key2"]["key3"] == "Hello"
    assert data["key2"]["key4"]["location"] == "NC"


def test_dict_pop():
    data = {
        "a": { "b": { "c": { "d": 1 } } },
        "aa": { "bb": { "e": { "x": 14 } } }
    }

    p1 = lib.dict_pop(data, "aa.bb.e.x")
    assert p1 == 14
    assert data["aa"] == {"bb": {"e": {}}}
    assert data ==  {'a': {'b': {'c': {'d': 1}}}, 'aa': {'bb': {'e': {}}}}


def test_flatten_dict():
    d1 = {
        "personal": {
            "name": {
                "first": "first name",
                "last": "last name"
            }
        },
        "location": {
            "city": "Charlotte"
        },
        "array": ["A", "B", "C"],
        "list_any": [{"k0": "v0", "d": { "d1" : { "d2": True}}}, 5, "Ok", True]
    }

    f1 = {
        "personal.name.first": "first name",
        "personal.name.last": "last name",
        "location.city": "Charlotte",
        "array": ["A", "B", "C"],
        "list_any": [{'d.d1.d2': True, 'k0': 'v0'}, 5, 'Ok', True]
    }

    assert lib.flatten_dict(d1) == f1


def test_unflatten_dict():
    d1 = {
        "personal": {
            "name": {
                "first": "first name",
                "last": "last name"
            }
        },
        "location": {
            "city": "Charlotte"
        },
        "array": ["A", "B", "C"],
        "list_any": [{"k0": "v0", "d": { "d1" : { "d2": True}}}, 5, "Ok", True]
    }

    f1 = {
        "personal.name.first": "first name",
        "personal.name.last": "last name",
        "location.city": "Charlotte",
        "array": ["A", "B", "C"],
        "list_any": [{'d.d1.d2': True, 'k0': 'v0'}, 5, 'Ok', True]
    }

    assert lib.unflatten_dict(f1) == d1


def test_dict_merge():
    a = {
        'a': 1,
        'b': {
            'b1': 2,
            'b2': 3,
        },
    }
    b = {
        'a': 1,
        'b': {
            'b1': 4,
            'b3': 5
        },
        'c': 6,
    }

    assert lib.dict_merge(a, b)['a'] == 1
    assert lib.dict_merge(a, b)['b']['b2'] == 3
    assert lib.dict_merge(a, b)['b']['b1'] == 4
    assert lib.dict_merge(b, a)['b']['b1'] == 2  # order is flipped
    assert lib.dict_merge(a, b)['b']['b3'] == 5  # new element
    assert lib.dict_merge(a, b)['c'] == 6  # new element


def test_chunk_list():
    data = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
    c = list(lib.chunk_list(data, 3))
    assert isinstance(c, list)
    assert isinstance(c[0], list)
    assert len(c) == 4
    assert len(c[len(c) - 1]) == 2


