import json
with open(r'test_login_credentials.json', 'r') as f:
            login = json.load(f)
            print(login['username'])
