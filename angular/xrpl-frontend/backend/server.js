const express = require('express');
const axios = require('axios');
const cors = require('cors'); // Import the cors middleware
const app = express();

// Enable CORS for all routes
app.use(cors());

app.use(express.json());

// Proxy endpoint for Xumm API
app.post('/api/xumm/payload', async (req, res) => {
  try {
    const response = await axios.post('https://xumm.app/api/v1/platform/payload', req.body, {
      headers: {
        'X-API-Key': req.headers['x-api-key'],
        'X-API-Secret': req.headers['x-api-secret'],
      },
    });
    console.log('Xumm API response:', response.data);
    res.json(response.data);
  } catch (error) {
    res.status(error.response?.status || 500).json(error.response?.data || { message: 'An error occurred' });
  }
});

// Endpoint to cancel or expire a payload (simulated, adjust based on Xumm API)
app.delete('/api/xumm/payload/:payloadId', async (req, res) => {
  const payloadId = req.params.payloadId;
  console.log(`Attempting to cancel payload with ID: ${payloadId}`);

  try {
    // Simulate cancellation by logging or handling locally (Xumm may not provide a direct cancellation API)
    // You can proxy to Xumm's API if they provide a cancellation endpoint, or handle it differently
    // For now, we'll return a success response as a simulation
    console.log('Xumm API response:', response.data);
    res.json({ message: `Payload ${payloadId} cancelled successfully (simulated)` });
  } catch (error) {
    console.error('Error cancelling payload:', error);
    res.status(500).json({ message: 'Failed to cancel payload' });
  }
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
});