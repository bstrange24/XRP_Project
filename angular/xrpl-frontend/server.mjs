import express from 'express';
import cors from 'cors';
import fetch from 'node-fetch';

const app = express();
app.use(express.json());

const corsOptions = {
  origin: 'http://localhost:4200',
  optionsSuccessStatus: 200,
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['x-api-key', 'x-api-secret', 'Content-Type', 'Accept'],
  credentials: true
};
app.use(cors(corsOptions));

// Middleware to log all incoming requests
app.use((req, res, next) => {
  console.log(`Incoming request: ${req.method} ${req.url} with headers:`, req.headers);
  next();
});

// Test endpoint to verify proxy
app.get('/test', (req, res) => {
  console.log('Test endpoint hit with query:', req.query);
  res.setHeader('Content-Type', 'application/json');
  res.json({ message: 'Proxy is working! Received request at /test', timestamp: new Date().toISOString() });
});

// Proxy endpoint for Xumm payload creation
app.post('/api/v1/platform/payload', async (req, res) => {
  const { 'x-api-key': apiKey, 'x-api-secret': apiSecret } = req.headers;

  if (!apiKey || !apiSecret) {
    return res.status(400).json({ error: 'API key and secret are required' });
  }

  console.log('Proxying request to Xumm API with headers:', { apiKey, apiSecret });
  try {
    const response = await fetch('https://xumm.app/api/v1/platform/payload', {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'x-api-secret': apiSecret,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(req.body)
    });

    if (!response.ok) {
      throw new Error(`Xumm API error: ${response.status} - ${response.statusText}`);
    }

    const data = await response.json();
    res.json(data);
  } catch (error) {
    console.error('Proxy error:', error);
    res.status(500).json({ error: 'Failed to forward request to Xumm API' });
  }
});

// Handle OPTIONS preflight requests for /api/v1/platform/payload
app.options('/api/v1/platform/payload', (req, res) => {
  console.log('Handling OPTIONS preflight for:', req.url, 'Headers:', req.headers);
  res.header('Access-Control-Allow-Origin', 'http://localhost:4200');
  res.header('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'x-api-key, x-api-secret, Content-Type, Accept');
  res.header('Access-Control-Max-Age', '86400');
  res.sendStatus(200);
});

// Handle OPTIONS preflight requests for /test
app.options('/test', (req, res) => {
  console.log('Handling OPTIONS preflight for test endpoint:', req.url, 'Headers:', req.headers);
  res.header('Access-Control-Allow-Origin', 'http://localhost:4200');
  res.header('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Accept');
  res.header('Access-Control-Max-Age', '86400');
  res.sendStatus(200);
});

const PORT = 3000;
app.listen(PORT, () => console.log(`Proxy server running on port ${PORT}`));