import requests
import json

query = """{
  __type(name: "MutationRoot") {
    fields {
      name
      args {
        name
        type {
          name
          kind
          ofType { name }
        }
      }
      type {
        name
        kind
        ofType { name }
      }
    }
  }
}"""

r = requests.post("http://192.168.1.150:8080/graphql", json={"query": query}, timeout=5)
data = r.json()
fields = data.get("data", {}).get("__type", {}).get("fields", [])
for f in fields:
    if "project" in f.get("name", "").lower():
        print(f.get("name"), "->", f.get("args"), "returns", f.get("type"))
