import pytest
from angola import kango
from kango.database import Database, Collection, Document

def test_create_db():
    db = kango()
    assert isinstance(db, Database)

def test_select_collection():
    db = kango()
    coll = db.select("collname")
    assert isinstance(coll, Collection)
    assert coll.name == "collname"

def test_select_collection_magic():
    db = kango()
    coll = db.collname
    assert isinstance(coll, Collection)

def test_select_collection_name_magic():
    db = kango()
    coll = db.collname
    assert coll.name == "collname"

def test_collection_size():
    db = kango()
    coll = db.collname

    for i in range(5):
        coll.insert({"name": "x"})
    assert coll.size == 5