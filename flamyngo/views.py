import json
import re
import os

from pymongo import MongoClient

from monty.serialization import loadfn
from monty.json import jsanitize

from flask import render_template, request, make_response

from flamyngo import app

module_path = os.path.dirname(os.path.abspath(__file__))


SETTINGS = loadfn(os.environ["FLAMYNGO"])
CONN = MongoClient(SETTINGS["db"]["host"], SETTINGS["db"]["port"])
DB = CONN[SETTINGS["db"]["database"]]
if "username" in SETTINGS["db"]:
    DB.authenticate(SETTINGS["db"]["username"], SETTINGS["db"]["password"])
CNAMES = [d["name"] for d in SETTINGS["collections"]]
CSETTINGS = {d["name"]: d for d in SETTINGS["collections"]}


@app.route('/', methods=['GET'])
def index():
    return make_response(render_template('index.html', collections=CNAMES))


@app.route('/query', methods=['GET'])
def query():
    cname = request.args.get("collection")
    search_string = request.args.get("search_string")
    settings = CSETTINGS[cname]

    criteria = {}
    for regex in settings["query"]:
        if re.match(r'%s' % regex[1], search_string):
            criteria[regex[0]] = parse_criteria(search_string, regex[2])
            break
    if not criteria:
        criteria = json.loads(search_string)
    results = []
    for r in DB[cname].find(criteria, projection=settings["summary"]):
        processed = {}
        for k in settings["summary"]:
            toks = k.split(".")
            val = r[toks[0]]
            try:
                for t in toks[1:]:
                    try:
                        val = val[t]
                    except KeyError:
                        # Handle integer indices
                        val = val[int(t)]
            except:
                # Return the base value if we can descend into the data.
                pass
            processed[k] = val
        results.append(processed)
    return make_response(render_template(
        'index.html', collection_name=cname,
        results=results, fields=settings["summary"],
        unique_key=settings["unique_key"],
        active_collection=cname,
        collections=CNAMES)
    )


@app.route('/<string:collection_name>/doc/<string:uid>')
def get_doc(collection_name, uid):
    settings = CSETTINGS[collection_name]
    criteria = {
        settings["unique_key"]: parse_criteria(uid, settings["unique_key_type"])}
    doc = DB[collection_name].find_one(criteria)
    return make_response(render_template(
        'doc.html', doc=json.dumps(jsanitize(doc)),
        collection_name=collection_name, doc_id=uid)
    )


def parse_criteria(val, vtype):
    toks = vtype.rsplit(".", 1)
    print(toks)
    if len(toks) == 1:
        func = getattr(__import__("__builtin__"), toks[0])
    else:
        mod = __import__(toks[0], globals(), locals(), [toks[1]], 0)
        func = getattr(mod, toks[1])
    print(func)

    return func(val)


if __name__ == "__main__":
    app.run(debug=True)
