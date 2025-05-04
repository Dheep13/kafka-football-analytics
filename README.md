# Real-Time Football Analytics with Python and Free APIs

A real-time football analytics application that uses free football APIs, Kafka for data streaming, and a Flask web dashboard for visualization.

## Features

- **Real-time match tracking**
  - Live scores and match status
  - Minute-by-minute updates

- **Statistical analysis**
  - Possession trends
  - Shot analysis
  - Team performance metrics

- **Visual dashboard**
  - Auto-refreshing web interface
  - Dynamic charts that update as new data arrives

## Architecture

The application follows a publish-subscribe architecture using Kafka:

1. **Data Collection Layer**
   - Fetches data from Football-Data.org API
   - Publishes data to Kafka topics:
     - `football-matches`: Upcoming and live matches
     - `football-live-updates`: Real-time match updates
     - `football-standings`: League standings
     - `football-teams`: Team information

2. **Processing Layer**
   - Consumes data from Kafka topics
   - Processes and stores football data in memory
   - Provides data to the presentation layer

3. **Presentation Layer**
   - Flask web application
   - Real-time updates via Socket.IO
   - Responsive web interface for desktop and mobile

### Benefits of Kafka Architecture

- **Decoupling**: Data collection and processing are decoupled, allowing each component to scale independently
- **Resilience**: Kafka provides message persistence, ensuring no data is lost even if components fail
- **Scalability**: Multiple consumers can process the same data for different purposes
- **Real-time**: Enables real-time data processing and updates to the user interface

## Project Structure

```
BigData Project/
├── kafka-docker-compose.yml  # Kafka setup
├── start_kafka.sh            # Script to start Kafka
├── start_kafka_app.sh        # Script to start the Kafka-based application
├── requirements.txt          # Dependencies
├── .env                      # API keys and configuration
├── src/
│   ├── config.py             # Configuration settings
│   ├── enhanced_app.py       # Standalone Flask application
│   ├── kafka_app.py          # Kafka-based application core
│   ├── kafka_web_app.py      # Kafka-based Flask application
│   ├── kafka_producer.py     # Sends data to Kafka
│   ├── kafka_consumer.py     # Consumes data from Kafka
│   ├── team_profile_app.py   # Standalone team profile application
│   └── utils.py              # Helper functions
└── templates/
    ├── layout.html           # Base template
    ├── index.html            # Dashboard
    ├── match_details.html    # Detailed match view
    ├── standings.html        # League standings
    ├── team_profile.html     # Team profile page
    └── team_list.html        # List of teams
```

## Setup Instructions

### Prerequisites

- Python 3.8+
- Docker and Docker Compose (for Kafka)
- Free API keys from:
  - [Football-Data.org](https://www.football-data.org/client/register)
  - [API-Football via RapidAPI](https://rapidapi.com/api-sports/api/api-football)

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd BigData\ Project
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file from the template:
   ```
   cp .env.example .env
   ```

4. Add your API keys to the `.env` file:
   ```
   FOOTBALL_DATA_API_KEY=your_api_key_here
   RAPID_API_KEY=your_rapid_api_key_here
   ```

### Running the Application

#### Option 1: Using the Kafka-based application

1. Start Kafka and the football application in one step:
   ```
   ./start_kafka_football_app.sh
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

#### Option 2: Manual startup with Kafka

1. Start Kafka using Docker Compose:
   ```
   docker-compose -f kafka-docker-compose.yml up -d
   ```

2. Start the Kafka-based football application:
   ```
   python src/kafka_football_app.py
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

#### Option 3: Running the standalone application (without Kafka)

1. Start the standalone application:
   ```
   python src/enhanced_app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

#### Option 4: Running the team profile application

1. Start the team profile application:
   ```
   python src/team_profile_app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5001
   ```

## API Usage

The application uses two free football APIs:

### Football-Data.org (Free Tier)
- 10 calls per minute
- Access to scores, matches, and basic statistics
- [Documentation](https://www.football-data.org/documentation/api)

### API-Football (Free Tier via RapidAPI)
- 100 requests per day (free)
- More detailed statistics
- [Documentation](https://www.api-football.com/documentation-v3)

## Limitations

- Free API tiers have rate limits
- Limited historical data
- Some advanced statistics may not be available

## License

This project is licensed under the MIT License - see the LICENSE file for details.
