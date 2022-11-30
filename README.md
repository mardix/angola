# Angola

**Angola**

## API

## Connection

```
import angola

#--- connect
db = angola.db(hosts="http://host:8529", username="root", password:str)

#--- select collection
coll = db.select_collection('test')

#--- insert item
coll.insert({k:v, ...})

#--- insert item with custom _key
coll.insert({k:v,...}, _key='awesome')


```

### Query 

### @@CURRDATE

`@@CURRDATE($format=None, $dateshifter=None) `



```
  {
    "_modified_at": "@@CURRDATE() +2Days"
  }
```

Format:

```
YYYY: Year
MM: Month
DD: Date
HH: Hour
mm: Min
ss: seconds

ISODATE: YYYY-MM-DDTHH:mm:ss

```


### $AND and $OR

```
filters = {

  "$or": [
    { // query between dates
      "_created_at:$lt": "@@CURRDATE() -2days",
      "_created_at:$gt": "@@CURRDATE() +2days"
    }
  ]
}
```

### Insert

### Update

### Delete

### Collection

### SubCollection



### Operators


### Custom Operators


