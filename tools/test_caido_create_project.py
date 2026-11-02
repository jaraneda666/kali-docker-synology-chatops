import requests
import json

token_res = requests.post('http://192.168.1.150:8080/graphql', json={'query': 'mutation { loginAsGuest { token { accessToken } } }'}).json()
token = token_res['data']['loginAsGuest']['token']['accessToken']
print("[*] Access Token:", token[:30] + "...")

headers = {'Authorization': f'Bearer {token}'}
q = """mutation {
  createProject(input: { name: "Audit_LAN_3000", temporary: true }) {
    project { id name }
    error { __typename }
  }
}"""
r = requests.post('http://192.168.1.150:8080/graphql', json={'query': q}, headers=headers)
res = r.json()
print('CREATE PROJECT RES:', res)

proj_id = res['data']['createProject']['project']['id']
q_sel = f'''mutation {{
  selectProject(id: "{proj_id}") {{
    project {{ id name }}
    error {{ __typename }}
  }}
}}'''
r2 = requests.post('http://192.168.1.150:8080/graphql', json={'query': q_sel}, headers=headers)
print('SELECT PROJECT RES:', r2.json())

