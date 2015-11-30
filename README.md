# mongologger

A Weechat script to log raw IRC messages to a MongoDB instance so you can you **BIG DATA NOSQL** while you IRC.

### Installation

This script relies on having the [pymongo](https://api.mongodb.org/python/current/#) module installed in a Python virtualenv located in `~/.weechat/python_env/`

### Configuration

- `plugins.var.python.mongologger.enabled`: Enables/disable logging
- `plugins.var.python.mongologger.mongo_host`: Hostname of your MongoDB instance (default: localhost)
- `plugins.var.python.mongologger.mongo_port`: Port of your MongoDB instance (default: 27017)
- `plugins.var.python.mongologger.mongo_database`: Database name (default: "irclogs")
- `plugins.var.python.mongologger.mongo_collection`: Collection to save logs to (default: "messages")
- `plugins.var.python.mongologger.mongo_user`: Username to authenticate with (optional)
- `plugins.var.python.mongologger.mongo_password`: Password to authenticate with (optional)

### Usage

Logging is disabled by default. To enable logging after you load mongologger.py be sure to set your configuration properties and then

```
/set plugins.var.python.mongologger.enabled on
```
