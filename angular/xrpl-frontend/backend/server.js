const express = require('express');
const axios = require('axios');
const cors = require('cors');
const app = express();

// Enable CORS for all routes, allowing specific headers
const corsOptions = {
  origin: 'http://localhost:4200',
  methods: ['GET', 'POST', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['X-API-Key', 'X-API-Secret', 'Content-Type', 'Accept'],
  credentials: true,
  optionsSuccessStatus: 200 // Some legacy browsers (IE11, various SmartTVs) choke on 204
};
app.use(cors(corsOptions));

app.use(express.json());

// Proxy endpoint for Xumm payload creation
app.post('/api/xumm/payload', async (req, res) => {
  console.log('Received payload request:', req.body, 'Headers:', req.headers);
  try {
    const response = await axios.post('https://xumm.app/api/v1/platform/payload', req.body, {
      headers: {
        'X-API-Key': req.headers['x-api-key'],
        'X-API-Secret': req.headers['x-api-secret'],
        'Content-Type': 'application/json'
      },
    });
    console.log('Xumm API response:', response.data);
    res.json(response.data);
  } catch (error) {
    console.error('Error proxying to Xumm:', error);
    res.status(error.response?.status || 500).json(error.response?.data || { message: 'An error occurred proxying to Xumm', details: error.message });
  }
});

// Proxy endpoint for Xumm payload status
app.get('/api/xumm/payload/:payloadId', async (req, res) => {
  const payloadId = req.params.payloadId;
  console.log(`Fetching payload status for ID: ${payloadId} with headers:`, req.headers);

  try {
    const response = await axios.get(`https://xumm.app/api/v1/platform/payload/${payloadId}`, {
      headers: {
        'X-API-Key': req.headers['x-api-key'],
        'X-API-Secret': req.headers['x-api-secret'],
      },
    });
    console.log('Xumm API payload status response:', response.data);
    if (!response.data || Object.keys(response.data).length === 0) {
      res.status(404).json({ message: 'Payload not found or expired', payloadId });
    } else {
      res.json(response.data);
    }
  } catch (error) {
    console.error('Error fetching payload status:', error);
    if (error.response && error.response.status === 404) {
      res.status(404).json({ message: 'Payload not found or expired', payloadId });
    } else {
      res.status(error.response?.status || 500).json(error.response?.data || { message: 'Failed to fetch payload status', payloadId, details: error.message });
    }
  }
});

// Endpoint to cancel or expire a payload (simulated, adjust based on Xumm API)
app.delete('/api/xumm/payload/:payloadId', async (req, res) => {
  const payloadId = req.params.payloadId;
  console.log(`Attempting to cancel payload with ID: ${payloadId}`);

  try {
    // Simulate cancellation by logging or handling locally (Xumm may not provide a direct cancellation API)
    res.json({ message: `Payload ${payloadId} cancelled successfully (simulated)` });
  } catch (error) {
    console.error('Error cancelling payload:', error);
    res.status(500).json({ message: 'Failed to cancel payload', details: error.message });
  }
});

// Handle OPTIONS preflight requests for all endpoints
app.options('/api/xumm/payload*', (req, res) => {
  res.header('Access-Control-Allow-Origin', 'http://localhost:4200');
  res.header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'X-API-Key, X-API-Secret, Content-Type, Accept');
  res.header('Access-Control-Max-Age', '86400');
  res.sendStatus(200);
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
});