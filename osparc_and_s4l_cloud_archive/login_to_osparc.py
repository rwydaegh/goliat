import os
from osparc import ApiClient, UsersApi

os.environ["OSPARC_API_KEY"] = "YOUR_OSPARC_API_KEY"
os.environ["OSPARC_API_SECRET"] = "YOUR_OSPARC_API_SECRET"
os.environ["OSPARC_API_BASE_URL"] = "https://api.sim4life.science"

# Initialize the API client
with ApiClient() as api_client:
    users_api = UsersApi(api_client)

    # Fetch and print user profile information
    profile = users_api.get_my_profile()
    print(profile)

    # Example output:
    # {'first_name': 'foo',
    #  'gravatar_id': 'aa33fssec77ea434c2ea4fb92d0fd379e',
    #  'groups': {'all': {'description': 'all users',
    #                     'gid': '1',
    #                     'label': 'Everyone'},
    #             'me': {'description': 'primary group',
    #                    'gid': '2',
    #                    'label': 'foo'},
    #             'organizations': []},
    #  'last_name': '',
    #  'login': 'foo@itis.swiss',
    #  'role': 'USER'}
