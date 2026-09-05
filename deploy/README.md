# Production deployment checklist

1. Use a Linux VM with a fixed public IPv4 address.
2. Register that public IP in the Kite developer console before enabling live orders.
3. Create `/opt/strategy-e`, a dedicated `strategy` OS user, and a Python virtualenv.
4. Copy the application and `.env` to `/opt/strategy-e`.
5. Set application timezone to `Asia/Kolkata`.
6. Put HTTPS in front of port 8081 (nginx/Caddy/load balancer).
7. Never expose port 8081 directly to the Internet.
8. Enable the systemd service only after preflight passes.
9. Keep `LIVE_ORDERS_ARMED=false` until the final go/no-go.
10. Test reboot recovery and broker reconciliation before live trading.
