# Virtual Fencing Technology for Rotational Grazing

A comprehensive IoT-based virtual fencing system designed for rotational grazing management, combining Bluetooth Low Energy (BLE) positioning, IMU motion detection, and real-time alert systems.

## System Architecture

### Overview
This system implements a three-layer architecture for intelligent livestock management:

1. **Sensor Layer**: BLE beacons, IMU sensors, and environmental monitoring devices
2. **Edge Computing Layer**: Gateway devices with local AI processing capabilities
3. **Cloud/Application Layer**: Web-based monitoring interface and alert management

### Core Components

#### Backend Services (`code_backend/`)
- **Positioning System**: RSSI-based grid positioning using KNN machine learning
- **Motion Detection**: IMU-based gesture and movement classification
- **Alert Management**: SMS notifications and buzzer control via Modbus TCP
- **Data Processing**: Real-time data sampling and model inference

#### Frontend Interface (`code_frontend/`)
- **Interactive Map**: Leaflet-based visualization with virtual fence boundaries
- **Real-time Monitoring**: Live position tracking and status updates
- **Alert Dashboard**: Visual representation of livestock positions and alerts

## Key Features

### 1. Intelligent Positioning
- **Grid-based Location System**: Divides grazing areas into configurable grid cells
- **BLE RSSI Analysis**: Uses signal strength from multiple receivers for accurate positioning
- **Machine Learning**: KNN model trained on historical RSSI data for improved accuracy
- **Missing Data Handling**: Intelligent imputation using historical patterns and column means

### 2. Motion Detection & Classification
- **IMU Sensor Integration**: Accelerometer and gyroscope data processing
- **Deep Learning Models**: 
  - CNN-based motion classifier for basic movements
  - BiLSTM with Multi-Head Attention for complex gesture recognition
- **Real-time Processing**: Edge-based inference for low-latency response

### 3. Alert & Notification System
- **SMS Alerts**: Automatic notifications when livestock cross virtual boundaries
- **Audio Alerts**: Buzzer control via Modbus TCP protocol
- **Visual Displays**: LCD screens with real-time status information
- **Configurable Thresholds**: Customizable alert conditions and response actions

### 4. Communication Infrastructure
- **MQTT Broker**: Centralized message routing and real-time data distribution
- **Modbus TCP**: Industrial protocol for device control and monitoring
- **Cellular Connectivity**: 4G SIM card integration for SMS and remote communication

## Technical Implementation

### Backend Architecture

#### Core Services
- **`predict_and_publish.py`**: Main prediction engine and MQTT publisher
- **`alarmHandler.py`**: Central alert management and device control
- **`dataSampling.py`**: Real-time data collection and preprocessing

#### Machine Learning Models
- **Positioning Model**: `model/weight/knn_model.pkl` - KNN classifier for grid prediction
- **IMU Models**: 
  - `IMU/weights/best_imu_net.pt` - CNN-based motion classifier
  - `IMU_2/imu_model.pt` - BiLSTM gesture recognition model

#### Device Control
- **`lib/buzzer_modbusTCP.py`**: Buzzer control via Modbus TCP
- **`lib/TwoLineLCD_ModbusTCP.py`**: LCD display management
- **`lib/publisher.py`**: MQTT message publishing utilities

### Frontend Implementation

#### Interactive Map Features
- **Virtual Fence Visualization**: Polygon-based boundary representation
- **Real-time Tracking**: Live position updates via MQTT subscription
- **Grid Overlay**: Canvas-based grid system for precise positioning
- **Responsive Design**: Zoom-based visibility controls and mobile optimization

#### Data Visualization
- **Position Markers**: Color-coded indicators for livestock status
- **Alert Overlays**: Visual notifications for boundary violations
- **Historical Trails**: Path tracking and movement analysis

## User Interface

### Web Dashboard
- **Real-time Map**: Interactive Leaflet-based interface
- **Status Monitoring**: Live livestock positions and fence status
- **Alert Management**: Visual and textual notification system
- **Configuration Panel**: Fence boundaries and alert settings

### Device Interfaces
- **LCD Displays**: Two-line status information with color coding
- **Audio Alerts**: Configurable buzzer patterns for different events
- **Physical Controls**: Modbus TCP-based device management

## Installation & Setup

### Prerequisites
```bash
# Python dependencies
pip install -r requirements.txt

# System requirements
- Python 3.8+
- MQTT Broker (e.g., Mosquitto)
- Modbus TCP compatible devices
- 4G SIM card for cellular connectivity
```

### Configuration
1. **MQTT Broker**: Update broker address in configuration files
2. **Device IPs**: Configure Modbus TCP device addresses
3. **SMS Settings**: Set up cellular provider and phone numbers
4. **Grid Layout**: Define virtual fence boundaries and grid dimensions


## Data Flow

### 1. Data Collection
- BLE RSSI values from multiple receivers
- IMU sensor data (acceleration, gyroscope)
- Environmental parameters and device status

### 2. Processing Pipeline
- **Data Preprocessing**: Cleaning, normalization, and missing value imputation
- **Feature Extraction**: RSSI pattern analysis and motion characteristics
- **Model Inference**: Real-time prediction using trained ML models
- **Decision Making**: Alert generation based on position and motion data

### 3. Output & Actions
- **MQTT Publishing**: Real-time data distribution to subscribers
- **SMS Notifications**: Immediate alerts for boundary violations
- **Device Control**: Buzzer activation and LCD updates
- **Web Updates**: Live dashboard refresh with current status

## Security & Reliability

### Data Protection
- **Encrypted Communication**: MQTT over TLS for secure data transmission
- **Access Control**: Authentication and authorization for device management
- **Data Validation**: Input sanitization and error handling

### System Reliability
- **Fault Tolerance**: Graceful degradation and error recovery
- **Logging & Monitoring**: Comprehensive logging for debugging and maintenance
- **Backup Systems**: Redundant communication paths and fallback mechanisms

## Testing & Validation

### Test Cases
- **Positioning Accuracy**: Grid prediction validation
- **Alert System**: SMS and buzzer functionality testing
- **Motion Detection**: IMU classification accuracy
- **Integration Testing**: End-to-end system validation

### Performance Metrics
- **Latency**: Real-time response time measurements
- **Accuracy**: Position prediction and motion classification precision
- **Reliability**: System uptime and error rates

## Future Enhancements

### Planned Features
- **Advanced Analytics**: Machine learning-based behavior prediction
- **Mobile Application**: Native mobile apps for field monitoring
- **Weather Integration**: Environmental factor consideration
- **Multi-species Support**: Extended livestock type compatibility

### Scalability Improvements
- **Distributed Processing**: Edge computing optimization
- **Cloud Integration**: Advanced analytics and storage solutions
- **API Development**: Third-party integration capabilities

## Contributing

### Development Guidelines
- Follow Python PEP 8 coding standards
- Implement comprehensive error handling
- Add unit tests for new functionality
- Update documentation for API changes

### Testing Requirements
- Unit test coverage for core functions
- Integration testing for device communication
- Performance testing for real-time operations

## License

This project is licensed under the terms specified in the LICENSE file.

## Support

For technical support and questions:
- Review the code documentation and comments
- Check the logs in the `logs/` directory
- Refer to the test cases in `testCases/` for usage examples

---

**Note**: This system is designed for agricultural and livestock management applications. Ensure proper testing and validation before deployment in production environments.