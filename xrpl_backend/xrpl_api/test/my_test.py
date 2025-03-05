# import sys
# print(sys.executable)  # Should match C:\app\python3.13.2\python.exe
# print(sys.path)
#
# import xrpl
# from xrpl.models.transactions import AccountSet
# print(f"xrpl-py version: {xrpl.__version__}")
# print(f"AccountSet module: {AccountSet.__module__}")
# print(dir(AccountSet))
# try:
#     print(f"AccountSet.Flag: {AccountSet.Flag}")
#     print(dir(AccountSet.Flag))
# except AttributeError as e:
#     print(f"Error: {e}")
from xrpl.models import AccountSetAsfFlag

from xrpl_backend.xrpl_api.constants.constants import ASF_FLAGS


def map_request_parameters_to_flag_variables():
    return {
        flag: getattr(AccountSetAsfFlag, flag.upper()) for flag in ASF_FLAGS
    }

print(map_request_parameters_to_flag_variables())