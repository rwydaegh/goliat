import s4l_v1
from s4l_v1._api.application import run_application, get_app_safe
if get_app_safe() is None:
    run_application()

import s4l_v1.document as document

document.Open('C:/Users/rwydaegh/Downloads/test.smash')

print(document.AllSimulations[0])
for server in document.AllSimulations[0].GetAvailableServers():
    print(server.Name)

