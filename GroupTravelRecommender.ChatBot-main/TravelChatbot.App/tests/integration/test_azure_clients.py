from unittest.mock import Mock
from dataclasses import replace
from config import Settings
from services.cloud import Language, openai_client


def test_both_endpoint_modes_can_construct_without_network():
    settings = Settings(demo_mode=True, openai_endpoint="https://fixture.openai.azure.com",
                        openai_api_key="fixture", openai_text_embeded_api_key="fixture")
    azure = openai_client(settings)
    compatible = openai_client(replace(settings, openai_api_mode="compatible",
                                      openai_endpoint="https://fixture.openai.azure.com/openai/v1/"))
    assert "fixture.openai.azure.com" in str(azure.base_url)
    assert "/openai/v1/" in str(compatible.base_url)
    azure.close()
    compatible.close()
