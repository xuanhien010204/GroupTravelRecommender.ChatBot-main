# TravelChatbot.App

An AI-powered travel assistant with an interactive chat interface that helps users discover, explore, and book tours in Vietnam. Built with Streamlit, Azure OpenAI, and AWS services.

## Key Features

- 💬 **Natural Language Interface**: Chat naturally about tours, heritage sites, and travel plans
- 🔍 **Smart Tour Search**: 
  - Search by location: "Show me tours in Hoi An"
  - Filter by price: "Find tours under 600,000 VND"
  - Combine criteria: "Tours in Hue under 700,000 VND"
- 🏛️ **Heritage Guide Information**:
  - Get AI-powered explanations about cultural and historical sites
  - Ask specific questions about local heritage
  - Contextual information from curated guide content
- ✅ **Tour Management**:
  - Register for tours using tour ID and phone number
  - View registered tours and booking details
  - Check tour availability and status
- 📄 **Pagination Support**:
  - Browse through multiple tour options
  - Explore extensive heritage information
  - Request more results as needed

## Technology Stack

- **Frontend**: Streamlit
- **AI/ML**: 
  - Azure OpenAI (GPT-4, text embeddings)
  - Pinecone (vector search)
- **AWS Services**:
  - DynamoDB (tour and user data)
  - S3 (heritage guide storage)
- **Languages/Frameworks**:
  - Python 3.10+
  - OpenAI API
  - Boto3 (AWS SDK)

## Setup Requirements

### 1. Python Environment
```bash
python -m pip install streamlit boto3 botocore python-dotenv openai pinecone-client
```

### 2. Environment Variables (.env)
```plaintext
# AWS Configuration
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=your_region
HERITAGE_GUIDE_S3_BUCKET=your_bucket_name

# Azure OpenAI Configuration
OPENAI_ENDPOINT=your_endpoint
OPENAI_API_KEY=your_api_key
OPENAI_DEPLOYMENT_NAME=your_deployment_name
OPENAI_TEXT_EMBEDED_API_KEY=your_embedding_key
OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME=your_embedding_deployment

# Pinecone Configuration
PINECONE_API_KEY=your_api_key
PINECONE_ENVIRONMENT=your_environment
```

### 3. Infrastructure Setup

#### DynamoDB Tables

1. **Tours Table**
   - Table Name: `Tours`
   - Primary Key: `place` (partition)
   - GSI: `tourId-index`
   - Key Attributes:
     ```
     tourId (String)
     place (String)
     startDate (Number)
     endDate (Number)
     price (Number)
     title (String)
     category (String)
     status (String)
     heritageGuide (String)
     ```

2. **UserTours Table**
   - Table Name: `UserTours`
   - Primary Key: `tourId` (partition), `phoneNumber` (sort)
   - GSI: `phoneNumber-createAt-index`
   - Key Attributes:
     ```
     tourId (String)
     phoneNumber (String)
     createAt (Number)
     startDate (Number)
     ```

#### Vector Databases (Pinecone)

1. **Tours Index**
   ```
   Name: tours
   Dimension: 1536
   Metric: cosine
   Environment: aws (serverless)
   ```

2. **Heritage Guides Index**
   ```
   Name: tour-heritage-guides
   Dimension: 1536
   Metric: cosine
   Environment: aws (serverless)
   ```

## Running the Application

1. Clone the repository
2. Set up environment variables
3. Start the Streamlit server:
   ```bash
   streamlit run app.py
   ```

## Project Structure

```
TravelChatbot.App/
├── app.py                 # Main Streamlit application
├── config.py             # Configuration and environment validation
├── requirements.txt      # Python dependencies
├── models/
│   ├── tour.py          # Tour data model
│   └── user_tour.py     # User registration model
├── tools/
│   ├── tour_tools.py    # Core business logic
│   └── tour_search.py   # Vector search implementation
└── utilities/
    ├── pdf_reader.py    # PDF processing utilities
    └── s3_utils.py      # S3 interaction helpers
```

## Contributing

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License

---

For support or questions, please open an issue in the repository.