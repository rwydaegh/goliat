Python


Type to search
oSPARC API clients
Basic Tutorial
Installation
Setup
Solvers Workflow
References
Basic Tutorial
Installation
Install the python client and check the installation as follows:

import importlib

if importlib.util.find_spec("osparc") is not None:
    ! pip install osparc
! python -c "import osparc; print(osparc.__version__)"
Copy to clipboardErrorCopied
Setup
To setup the client, we need to provide a username and password to the configuration. These can be obtained in the UI under Preferences > API Settings > API Keys. Use the API key as username and the API secret as password. These should be specified as environment variables "OSPARC_API_KEY" and "OSPARC_API_SECRET" respectively. In addition you can specify the osparc endpoint you want to use (e.g. https://api.osparc.io) via the environment variable "OSPARC_API_HOST".

The functions in the osparc API are grouped into sections such as meta, users, files, solvers, studies, wallets and credits. Each section address a different resource of the platform.

For example, the users section includes functions about the user (i.e. you) and can be accessed initializing a UsersApi:

from osparc import ApiClient, UsersApi

with ApiClient() as api_client:
    users_api = UsersApi(api_client)

    profile = users_api.get_my_profile()
    print(profile)

    #
    #  {'first_name': 'foo',
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
    #
Copy to clipboardErrorCopied
Solvers Workflow
The osparc API can be used to execute any computational service published in the platform. This means that any computational service listed in the UI under the Services Tab is accessible from the API. Note that computational services are denoted as solvers in the API for convenience, but they refer to the same concept.

Let's use the sleepers computational service to illustrate a typical workflow. The sleepers computational service is a very basic service that simply waits (i.e. sleeps) a given time before producing some outputs. It takes as input one natural number, an optional text file input that contains another natural number and a boolean in the form of a checkbox. It also provides two outputs: one natural number and a file containing a single natural number.

import time
from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

import osparc

Path("file_with_number.txt").write_text("3")

with osparc.ApiClient() as api_client:
    files_api = osparc.FilesApi(api_client)
    input_file: osparc.File = files_api.upload_file(file="file_with_number.txt")

    solver_key: str = "simcore/services/comp/itis/sleeper"
    solver_version: str = "2.1.6"

    solvers_api = osparc.SolversApi(api_client)
    solver: osparc.Solver = solvers_api.get_solver_release(
        solver_key=solver_key, version=solver_version
    )

    solver_ports = solvers_api.list_solver_ports(solver.id, solver.version)
    print(f"solver_ports: {solver_ports}")

    job: osparc.Job = solvers_api.create_job(
        solver.id,
        solver.version,
        osparc.JobInputs(
            {
                "input_4": 2,
                "input_3": "false",
                "input_2": 3,
                "input_1": input_file,
            }
        ),
    )

    status: osparc.JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
    while not status.stopped_at:
        time.sleep(3)
        status = solvers_api.inspect_job(solver.id, solver.version, job.id)
        print("Solver progress", f"{status.progress}/100", flush=True)
    assert status.state == "SUCCESS"

    #
    # Solver progress 0/100
    # Solver progress 100/100

    outputs: osparc.JobOutputs = solvers_api.get_job_outputs(
        solver.id, solver.version, job.id
    )

    print(f"Job {outputs.job_id} got these results:")
    for output_name, result in outputs.results.items():
        print(output_name, "=", result)

    #
    # Job 19fc28f7-46fb-4e96-9129-5e924801f088 got these results:
    #
    # output_1 = {'checksum': '859fda0cb82fc4acb4686510a172d9a9-1',
    # 'content_type': 'text/plain',
    # 'filename': 'single_number.txt',
    # 'id': '9fb4f70e-3589-3e9e-991e-3059086c3aae'}
    # output_2 = 4.0

    logfile_path: str = solvers_api.get_job_output_logfile(
        solver.id, solver.version, job.id
    )
    zip_path = Path(logfile_path)

    with TemporaryDirectory() as tmp_dir:
        with ZipFile(f"{zip_path}") as fzip:
            fzip.extractall(tmp_dir)
        logfiles = list(Path(tmp_dir).glob("*.log*"))
        print("Unzipped", logfiles[0], "contains:\n", logfiles[0].read_text())
    #
    # Unzipped extracted/sleeper_2.0.2.logs contains:
    # 2022-06-01T18:15:00.405035847+02:00 Entrypoint for stage production ...
    # 2022-06-01T18:15:00.421279969+02:00 User : uid=0(root) gid=0(root) groups=0(root)
    # 2022-06-01T18:15:00.421560331+02:00 Workdir : /home/scu
    # ...
    # 2022-06-01T18:15:00.864550043+02:00
    # 2022-06-01T18:15:03.923876794+02:00 Will sleep for 3 seconds
    # 2022-06-01T18:15:03.924473521+02:00 [PROGRESS] 1/3...
    # 2022-06-01T18:15:03.925021846+02:00 Remaining sleep time 0.9999995231628418
    # 2022-06-01T18:15:03.925558026+02:00 [PROGRESS] 2/3...
    # 2022-06-01T18:15:03.926103062+02:00 Remaining sleep time 0.9999985694885254
    # 2022-06-01T18:15:03.926643184+02:00 [PROGRESS] 3/3...
    # 2022-06-01T18:15:03.933544384+02:00 Remaining sleep time 0.9999983310699463

    download_path: str = files_api.download_file(file_id=outputs.results["output_1"].id)
    print(Path(download_path).read_text())
    #
    # 7
Copy to clipboardErrorCopied
The script above

Uploads a file file_with_number.txt
Selects version 2.0.2 of the sleeper
Runs the sleeper and provides a reference to the uploaded file and other values as input parameters
Monitors the status of the solver while it is running in the platform
When the execution completes, it checks the outputs
The logs are downloaded, unzipped and saved to a new extracted directory
One of the outputs is a file and it is downloaded
Files
Files used as input to solvers or produced by solvers in the platform are accessible in the files section and specifically with the FilesApi class. In order to use a file as input, it has to be uploaded first and the reference used in the corresponding solver's input.

files_api = FilesApi(api_client)
input_file: File = files_api.upload_file(file="file_with_number.txt")


# ...


outputs: JobOutputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)
results_file: File = outputs.results["output_1"]
download_path: str = files_api.download_file(file_id=results_file.id)
Copy to clipboardErrorCopied
In the snippet above, input_file is a File reference to the uploaded file and that is passed as input to the solver. Analogously, results_file is a File produced by the solver and that can also be downloaded.

Solvers, Inputs and Outputs
The inputs and outputs are specific for every solver. Every input/output has a name and an associated type that can be as simple as booleans, numbers, strings ... or more complex as files. You can find this information in the UI under Services Tab, selecting the service card > Information > Raw metadata. For instance, the sleeper version 2.0.2 has the following raw-metadata:

{
 "inputs": {
  "input_1": {
   "displayOrder": 1,
   "label": "File with int number",
   "description": "Pick a file containing only one integer",
   "type": "data:text/plain",
   "fileToKeyMap": {
    "single_number.txt": "input_1"
   },
   "keyId": "input_1"
  },
  "input_2": {
   "unitLong": "second",
   "unitShort": "s",
   "label": "Sleep interval",
   "description": "Choose an amount of time to sleep in range [0-65]",
   "keyId": "input_2",
   "displayOrder": 2,
   "type": "ref_contentSchema",
   "contentSchema": {
    "title": "Sleep interval",
    "type": "integer",
    "x_unit": "second",
    "minimum": 0,
    "maximum": 65
   },
   "defaultValue": 2
  },
  "input_3": {
   "displayOrder": 3,
   "label": "Fail after sleep",
   "description": "If set to true will cause service to fail after it sleeps",
   "type": "boolean",
   "defaultValue": false,
   "keyId": "input_3"
  },
  "input_4": {
   "unitLong": "meter",
   "unitShort": "m",
   "label": "Distance to bed",
   "description": "It will first walk the distance to bed",
   "keyId": "input_4",
   "displayOrder": 4,
   "type": "ref_contentSchema",
   "contentSchema": {
    "title": "Distance to bed",
    "type": "integer",
    "x_unit": "meter"
   },
   "defaultValue": 0
  }
 }
Copy to clipboardErrorCopied
So, the inputs can be set as follows

# ...
job: osparc.Job = solvers_api.create_job(
    solver.id,
    solver.version,
    osparc.JobInputs(
        {
            "input_4": 2,
            "input_3": "false",
            "input_2": 3,
            "input_1": input_file,
        }
    ),
)
Copy to clipboardErrorCopied
And the metadata for the outputs are

  "output_1": {
   "displayOrder": 1,
   "label": "File containing one random integer",
   "description": "Integer is generated in range [1-9]",
   "type": "data:text/plain",
   "fileToKeyMap": {
    "single_number.txt": "output_1"
   },
   "keyId": "output_1"
  },
  "output_2": {
   "unitLong": "second",
   "unitShort": "s",
   "label": "Random sleep interval",
   "description": "Interval is generated in range [1-9]",
   "keyId": "output_2",
   "displayOrder": 2,
   "type": "ref_contentSchema",
   "contentSchema": {
    "title": "Random sleep interval",
    "type": "integer",
    "x_unit": "second"
   }
Copy to clipboardErrorCopied
so this information determines which output corresponds to a number or a file in the following snippet

# ...

outputs: JobOutputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)

output_file = outputs.results["output_1"]
number = outputs.results["output_2"]

assert status.state == "SUCCESS"


assert isinstance(output_file, File)
assert isinstance(number, float)

# output file exists
assert files_api.get_file(output_file.id) == output_file

# can download and open
download_path: str = files_api.download_file(file_id=output_file.id)
assert float(Path(download_path).read_text()), "contains a random number"
Copy to clipboardErrorCopied
Job Status
Once the client script triggers the solver, the solver runs in the platform and the script is freed. Sometimes, it is convenient to monitor the status of the run to see e.g. the progress of the execution or if the run was completed.

A solver runs in a plaforma starts a Job. Using the solvers_api, allows us to inspect the Job and get a JobStatus with information about its status. For instance

 status: JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
 while not status.stopped_at:
     time.sleep(3)
     status = solvers_api.inspect_job(solver.id, solver.version, job.id)
     print("Solver progress", f"{status.progress}/100", flush=True)
Copy to clipboardErrorCopied
Logs
When a solver runs, it will generate logs during execution which are then saved as .log files. Starting from the osparc Python Client version 0.5.0, The solvers_api also allows us to obtain the logfile_path associated with a particular Job. This is a zip file that can then be extracted and saved. For instance

logfile_path: str = solvers_api.get_job_output_logfile(
    solver.id, solver.version, job.id
)
zip_path = Path(logfile_path)

extract_dir = Path("./extracted")
extract_dir.mkdir()

with ZipFile(f"{zip_path}") as fzip:
    fzip.extractall(f"{extract_dir}")
Copy to clipboardErrorCopied
References
osparc API python client documentation
osparc API documentation
A full script with this tutorial: sleeper.py
Download as BasicTutorial_v0.8.0.ipynb

