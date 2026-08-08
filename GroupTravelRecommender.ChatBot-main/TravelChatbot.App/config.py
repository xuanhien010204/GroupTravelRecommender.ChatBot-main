import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME")
OPENAI_TEXT_EMBEDED_API_KEY = os.getenv("OPENAI_TEXT_EMBEDED_API_KEY")
OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME = os.getenv("OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME")

# Pinecone Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
HERITAGE_GUIDE_S3_BUCKET = os.getenv("HERITAGE_GUIDE_S3_BUCKET")

# Validate configuration
def validate_config():
    """Validate that all required environment variables are set"""
    required_vars = [
        ("OPENAI_API_KEY", OPENAI_API_KEY),
        ("OPENAI_ENDPOINT", OPENAI_ENDPOINT),
        ("OPENAI_DEPLOYMENT_NAME", OPENAI_DEPLOYMENT_NAME),
        ("OPENAI_TEXT_EMBEDED_API_KEY", OPENAI_TEXT_EMBEDED_API_KEY),
        ("OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME", OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME),
        ("PINECONE_API_KEY", PINECONE_API_KEY),
        ("PINECONE_ENVIRONMENT", PINECONE_ENVIRONMENT),
        ("AWS_ACCESS_KEY_ID", AWS_ACCESS_KEY_ID),
        ("AWS_SECRET_ACCESS_KEY", AWS_SECRET_ACCESS_KEY),
        ("AWS_REGION", AWS_REGION),
        ("HERITAGE_GUIDE_S3_BUCKET", HERITAGE_GUIDE_S3_BUCKET),
    ]
    
    missing_vars = []
    for var_name, var_value in required_vars:
        if not var_value:
            missing_vars.append(var_name)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return True
