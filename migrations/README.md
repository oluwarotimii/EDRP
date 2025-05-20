# Database Migrations

This directory contains database migration scripts for the School ERP system.

## Overview

We use Alembic for database migrations. Migrations allow us to track, manage, and apply database schema changes over time.

## Structure

- `versions/`: Contains the individual migration scripts
- `env.py`: Alembic environment configuration
- `script.py.mako`: Template for new migration files

## Common Commands

### Create a New Migration

To create a new migration based on model changes:

```bash
alembic revision --autogenerate -m "Description of changes"
