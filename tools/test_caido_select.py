import requests
token_res = requests.post('http://192.168.1.150:8080/graphql', json={'query': 'mutation { loginAsGuest { token { accessToken } } }'}).json()
token = token_res['data']['loginAsGuest']['token']['accessToken']
headers = {'Authorization': f'Bearer {token}'}

q = """mutation {
  selectProject(id: "4125c3a1-61a2-44c2-82f6-8b62c293b1fb") {
    currentProject { project { id name } }
    error { __typename }
  }
}"""
r = requests.post('http://192.168.1.150:8080/graphql', json={'query': q}, headers=headers)
print('SELECT PROJECT:', r.json())

# Query current project
q_curr = "{ currentProject { project { id name } } }"
r2 = requests.post('http://192.168.1.150:8080/graphql', json={'query': q_curr}, headers=headers)
print('CURRENT PROJECT:', r2.json())
