import os
from src.util.llm_client.get_llm_client import get_llm_client

config_file = os.path.join("data", "llm_config", "cmhh_phase1.json")
llm_client = get_llm_client(config_file=config_file)
llm_client.load("Hi. Are you awake?")
response = llm_client.chat()
print(response)