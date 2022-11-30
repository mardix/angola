import pytest
from angola import dict_mutator

def test_mutate_simple_set():
  init_data = {
    "name": "mutate",
    "version": "1.0.2"
  }

  mutations = {
    "version": "2.0.1",
    "location": "CLT"
  }

  d, _ = dict_mutator.mutate(mutations)
  assert d["version"] == "2.0.1"

def test_incr():
  init_data = {
    "counter": 2
  }
  m = {
    "counter:$incr": True
  }

  d, _ = dict_mutator.mutate(mutations=m, init_data=init_data)
  assert d.get("counter") == 3

  m = {
    "counter:$incr": 5
  }
  d, _ = dict_mutator.mutate(mutations=m, init_data=init_data)
  assert d.get("counter") == 7

  m = {
    "counter:$incr": -3
  }
  d, _ = dict_mutator.mutate(mutations=m, init_data=init_data)
  assert d.get("counter") == -1
 

def test_decr():
  init_data = {
    "counter": 2
  }
  m = {
    "counter:$decr": True
  }

  d, _ = dict_mutator.mutate(mutations=m, init_data=init_data)
  assert d.get("counter") == 1

  m = {
    "counter:$decr": 5
  }
  d, _ = dict_mutator.mutate(mutations=m, init_data=init_data)
  assert d.get("counter") == -3

  m = {
    "counter:$decr": -3
  }
  d, _ = dict_mutator.mutate(mutations=m, init_data=init_data)
  assert d.get("counter") == 5