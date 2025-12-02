import React, { useState, useEffect } from 'react';
import { Typography, Paper, Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Chip } from '@mui/material';
import axios from 'axios';

interface PriceData {
  instance_type: string;
  availability_zone: string;
  current_price: number;
  average_price_24h: number;
  min_price_24h: number;
  max_price_24h: number;
  updated_at: string;
}

const PricingData: React.FC = () => {
  const [priceData, setPriceData] = useState<PriceData[]>([]);

  useEffect(() => {
    fetchPriceData();
    const interval = setInterval(fetchPriceData, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchPriceData = async () => {
    try {
      const response = await axios.get('/api/v1/pricing/current');
      setPriceData(response.data.prices || []);
    } catch (error) {
      console.error('Failed to fetch pricing data:', error);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Spot Pricing Data</Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Real-time Spot instance pricing across availability zones
      </Typography>

      <TableContainer sx={{ mt: 2 }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Instance Type</TableCell>
              <TableCell>Availability Zone</TableCell>
              <TableCell>Current Price</TableCell>
              <TableCell>24h Average</TableCell>
              <TableCell>24h Min</TableCell>
              <TableCell>24h Max</TableCell>
              <TableCell>Updated</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {priceData.map((price, idx) => (
              <TableRow key={idx}>
                <TableCell>{price.instance_type}</TableCell>
                <TableCell>{price.availability_zone}</TableCell>
                <TableCell>
                  <Chip label={`$${price.current_price.toFixed(4)}/hr`} size="small" color="primary" />
                </TableCell>
                <TableCell>${price.average_price_24h.toFixed(4)}</TableCell>
                <TableCell>${price.min_price_24h.toFixed(4)}</TableCell>
                <TableCell>${price.max_price_24h.toFixed(4)}</TableCell>
                <TableCell>{new Date(price.updated_at).toLocaleTimeString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
};

export default PricingData;
