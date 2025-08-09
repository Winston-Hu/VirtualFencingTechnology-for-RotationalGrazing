// MQTT Configuration
const MQTT_CONFIG = {
    broker: '10.166.179.5',
    port: 9001,
    //topic: '/modelPublish',
    topic: '/NoraPublish',
    clientId: 'webClient_' + Math.random().toString(16).substr(2, 8)
};

// MQTT client instance
let mqttClient = null;

// Store latest cow data
let latestCowData = [];

// Initialize MQTT connection
function initMQTTConnection() {
    const url = `ws://${MQTT_CONFIG.broker}:${MQTT_CONFIG.port}`;

    console.log('Connection URL:', url);
    console.log('Client ID:', MQTT_CONFIG.clientId);
    console.log('Subscribe Topic:', MQTT_CONFIG.topic);

    // Create MQTT client
    mqttClient = mqtt.connect(url, {
        clientId: MQTT_CONFIG.clientId,
        clean: true,
        reconnectPeriod: 1000,
        connectTimeout: 30 * 1000,
        keepalive: 60
    });

    // Connection success event
    mqttClient.on('connect', function() {
        console.log('SUCCESS: MQTT connection successful');
        console.log('Time:', new Date().toLocaleString());

        // Subscribe to topic
        mqttClient.subscribe(MQTT_CONFIG.topic, { qos: 1 }, function(err) {
            if (err) {
                console.error('ERROR: Subscription failed:', err);
            } else {
                console.log('SUCCESS: Successfully subscribed to topic:', MQTT_CONFIG.topic);
            }
        });
    });

    // Message received event
    mqttClient.on('message', function(topic, message) {
        console.log('\n Received MQTT Message');
        console.log('Time:', new Date().toLocaleString());
        console.log('Topic:', topic);
        console.log('Raw Message:', message.toString());

        try {
            const data = JSON.parse(message.toString());
            processReceivedData(data);
        } catch (e) {
            console.error('ERROR: JSON parsing failed:', e.message);
        }
    });

    // Connection error event
    mqttClient.on('error', function(err) {
        console.error('ERROR: MQTT connection error:', err.message);
    });

    // Disconnect event
    mqttClient.on('close', function() {
        console.log('DISCONNECT: MQTT connection closed');
    });

    // Reconnect event
    mqttClient.on('reconnect', function() {
        console.log('RECONNECT: Reconnecting to MQTT...');
    });

    // Offline event
    mqttClient.on('offline', function() {
        console.log('OFFLINE: MQTT client offline');
    });
}

// Process received data
function processReceivedData(data) {
    latestCowData = [];

    if (typeof data === 'object' && data !== null) {
        console.log(`Received data for ${Object.keys(data).length} cows:`);

        for (const [cowId, cowArray] of Object.entries(data)) {
            // Check if data format is correct [x, y, status]
            if (Array.isArray(cowArray) && cowArray.length >= 3) {
                const cowObj = {
                    id: cowId,
                    pos: [cowArray[0], cowArray[1]],
                    status: cowArray[2]
                };
                latestCowData.push(cowObj);
                console.log(`${cowId} - Position: [${cowObj.pos[0]}, ${cowObj.pos[1]}], Status: ${cowObj.status === 0 ? 'Safe' : 'Escaped'} (${cowObj.status}) `);
            }
        }

        // Update canvas display
        updateCowPositions(latestCowData);

    }
}

// Update cow position display
function updateCowPositions(cowData) {
    console.log('Current Cow Data:', cowData);
    // Call function in map.js to update cow positions
    if (typeof window.updateCowPositions === 'function') {
        window.updateCowPositions(cowData);
    }
}

// Get latest cow data
function getLatestCowData() {
    return latestCowData;
}

// Disconnect
function disconnectMQTT() {
    if (mqttClient) {
        console.log('\nDisconnecting MQTT connection...');
        mqttClient.end(true, {}, function() {
            console.log('[SUCCESS] MQTT connection safely disconnected');
        });
    }
}

// Get connection status
function getConnectionStatus() {
    if (mqttClient) {
        return {
            connected: mqttClient.connected,
            reconnecting: mqttClient.reconnecting,
            clientId: MQTT_CONFIG.clientId,
            broker: MQTT_CONFIG.broker,
            port: MQTT_CONFIG.port
        };
    }
    return null;
}

// Auto initialize after page load
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function() {
        initMQTTConnection();
    });
}

// Export functions for other modules to use
if (typeof window !== 'undefined') {
    window.MQTTReceiver = {
        init: initMQTTConnection,
        disconnect: disconnectMQTT,
        getStatus: getConnectionStatus,
        getLatestData: getLatestCowData
    };
}