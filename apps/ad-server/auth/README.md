# AdPilot Authentication Module

## Overview
Authentication system for advertiser/publisher accounts with API keys, OAuth2, and RBAC.

## Files
- `apps/ad-server/auth.py` - Authentication logic
- `apps/ad-server/models.py` - User and API key models
- `apps/ad-server/middleware.py` - Auth middleware and RBAC
- `apps/ad-server/routes/auth.py` - Auth API routes

## Features
- Advertiser and publisher account registration/login
- JWT-based session management
- API key generation and validation
- OAuth2 provider integration
- Role-Based Access Control (RBAC)
- Password hashing with scrypt
- Session timeout handling

## Tech Stack
- Python/FastAPI
- PostgreSQL
- JWT (PyJWT)
- OAuth2 (python-oauth2)
- bcrypt/scrypt for password hashing

## Day 5 Outcome
Authentication module implemented. 1 PR created targeting development.