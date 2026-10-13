# CineMatch - AWS Cloud Deployment Architecture
## Simple, Right-Sized Production Deployment

---

## 📋 Executive Summary

This document outlines the **minimal AWS architecture** for deploying CineMatch. The design uses only **5 essential services** - no over-engineering, just what's actually needed for a production-ready movie recommendation system.

**Current Status**: Fully functional locally  
**AWS Services Used**: 5 (EC2, RDS, S3, CloudWatch, Secrets Manager)  
**Estimated Migration Time**: 1 day  
**Cost Estimate**: ~$30-50/month  

---

## 🏗️ AWS Architecture Overview (Simplified)

### High-Level Architecture Diagram

```
                        ┌──────────────────┐
                        │      Users       │
                        │   (Web Browser)  │
                        └────────┬─────────┘
                                 │ HTTPS
                                 │
                    ┌────────────▼────────────┐
                    │      Amazon EC2         │
                    │  (t3.medium instance)   │
                    │                         │
                    │  ┌──────────────────┐   │
                    │  │   FastAPI App    │   │
                    │  │   (Uvicorn)      │   │
                    │  │   Port 8000      │   │
                    │  └──────────────────┘   │
                    │                         │
                    │  ┌──────────────────┐   │
                    │  │  Static Files    │   │
                    │  │  (Frontend)      │   │
                    │  └──────────────────┘   │
                    └─────────┬───────────────┘
                              │
                 ┌────────────┼────────────┐
                 │            │            │
         ┌───────▼──────┐ ┌──▼──────┐ ┌──▼──────────┐
         │  Amazon RDS  │ │ AWS S3  │ │   Secrets   │
         │ (PostgreSQL) │ │ Storage │ │   Manager   │
         │              │ │         │ │             │
         │ - User data  │ │ - Data  │ │ - API keys  │
         │ - Ratings    │ │ - Models│ │ - DB creds  │
         └──────────────┘ └─────────┘ └─────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   CloudWatch      │
                    │  (Logs & Alerts)  │
                    └───────────────────┘
```

**That's it!** Just 5 AWS services instead of 11.

---

## 🔧 AWS Services Used (Only What's Needed)

### 1. **Amazon EC2** (Virtual Server)


**Purpose**: Run the FastAPI application on a single server

**Why EC2 instead of Lambda?**
- ✅ Your app is already working - just move it to a cloud server
- ✅ No code changes needed (same uvicorn command)
- ✅ Simpler to understand and manage
- ✅ No cold starts
- ✅ Can handle all requests on one instance

**Configuration**:
```yaml
Instance Type: t3.medium (2 vCPU, 4GB RAM)
Operating System: Ubuntu 22.04 LTS
Storage: 30GB SSD
Region: us-east-1 (or closest to users)

Security Group (Firewall):
  - Port 80: HTTP (open to internet)
  - Port 443: HTTPS (open to internet)
  - Port 22: SSH (your IP only, for management)
```

**What runs on it**:
```bash
# Same setup as local, but on cloud server
├── FastAPI app (uvicorn src.app:app --host 0.0.0.0 --port 8000)
├── Frontend (served by FastAPI at /)
├── Python dependencies (pandas, scikit-learn, etc.)
└── Nginx (reverse proxy for HTTPS)
```

**Setup Commands**:
```bash
# Install dependencies
sudo apt update
sudo apt install python3.11 python3-pip nginx -y

# Clone your code
git clone <your-repo>
cd movie-recommender

# Install Python packages
pip install -r requirements.txt

# Set up environment variables
nano .env  # Add GROQ_API_KEY, SECRET_KEY, etc.

# Run the app (production mode)
uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers 2

# Set up Nginx for HTTPS (optional but recommended)
sudo nano /etc/nginx/sites-available/cinematch
# Configure reverse proxy: nginx → localhost:8000
```

**Estimated Cost**: $26/month (t3.medium on-demand pricing)

---

### 2. **Amazon RDS (PostgreSQL)** (Database)

**Purpose**: Store user accounts and preferences

**Why RDS?**
- ✅ Managed database (automatic backups, updates)
- ✅ Easy migration from SQLite
- ✅ Secure and reliable

**Configuration**:
```yaml
Engine: PostgreSQL 15
Instance: db.t3.micro (1 vCPU, 1GB RAM)
Storage: 20GB
Backup: 7 days retention
Multi-AZ: No (for cost savings; enable for production HA)
```

**Tables** (same as SQLite):
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(40) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_genres (
    user_id INTEGER REFERENCES users(id),
    genre VARCHAR(50),
    PRIMARY KEY (user_id, genre)
);
```

**Migration from SQLite**:
```bash
# Export from SQLite
sqlite3 data/users.db .dump > export.sql

# Import to PostgreSQL (modify schema for PostgreSQL syntax)
psql -h <rds-endpoint>.rds.amazonaws.com -U postgres -d cinematch -f export.sql
```

**Connection String** (stored in Secrets Manager):
```
postgresql://postgres:password@cinematch.xyz.rds.amazonaws.com:5432/cinematch
```

**Estimated Cost**: $15/month (db.t3.micro)

---

### 3. **Amazon S3** (File Storage)

**Purpose**: Store processed data files (Parquet) and ML models

**Why S3?**
- ✅ Cheap storage ($0.023 per GB/month)
- ✅ Durable (99.999999999% durability)
- ✅ EC2 can read files directly via AWS SDK

**Bucket Structure**:
```
s3://cinematch-data/
├── processed/
│   ├── movies.parquet           # 10,322 movies
│   ├── ratings.parquet          # 105,332 ratings
│   ├── genre_matrix.parquet     # TF-IDF vectors
│   └── user_movie_matrix.parquet # Collaborative matrix
└── models/
    └── (future: pre-trained ML models)
```

**How it's used**:
```python
# In your FastAPI app (startup)
import boto3
import pandas as pd

s3 = boto3.client('s3')

# Download Parquet files to EC2 instance
s3.download_file('cinematch-data', 'processed/movies.parquet', '/tmp/movies.parquet')
movies_df = pd.read_parquet('/tmp/movies.parquet')

# Files loaded once at startup, cached in memory
```

**Upload Data** (one-time setup):
```bash
# From your local machine
aws s3 sync data/processed/ s3://cinematch-data/processed/
```

**Estimated Cost**: $0.50/month (5GB data + minimal requests)

---

### 4. **AWS Secrets Manager** (Secure Secrets)

**Purpose**: Store sensitive credentials (API keys, database passwords)

**Why Secrets Manager?**
- ✅ Never commit secrets to code
- ✅ EC2 retrieves secrets at runtime
- ✅ Encrypted storage

**Secrets Stored**:
```json
{
  "cinematch/prod": {
    "DB_HOST": "cinematch.xyz.rds.amazonaws.com",
    "DB_USER": "postgres",
    "DB_PASSWORD": "super-secure-password-here",
    "GROQ_API_KEY": "gsk_xxxxxxxxxxxxxxxxxx",
    "SECRET_KEY": "jwt-signing-key-256-bits"
  }
}
```

**How to use in code**:
```python
import boto3
import json

def get_secrets():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    secret = client.get_secret_value(SecretId='cinematch/prod')
    return json.loads(secret['SecretString'])

secrets = get_secrets()
DB_HOST = secrets['DB_HOST']
GROQ_API_KEY = secrets['GROQ_API_KEY']
```

**Estimated Cost**: $0.40/month (1 secret)

---

### 5. **Amazon CloudWatch** (Monitoring)

**Purpose**: View logs and set up alerts

**Why CloudWatch?**
- ✅ Automatically collects EC2 logs
- ✅ Set alarms for errors or high CPU
- ✅ Free tier covers basic usage

**What's monitored**:
```yaml
Metrics:
  - EC2 CPU utilization
  - EC2 memory usage
  - RDS database connections
  - RDS disk space
  
Logs:
  - FastAPI application logs
  - Nginx access logs
  - System logs (syslog)

Alarms:
  - CPU > 80% for 5 minutes → Email notification
  - RDS storage < 2GB → Email notification
  - Application errors > 10/hour → Email notification
```

**Setup on EC2**:
```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure to send logs
sudo nano /opt/aws/amazon-cloudwatch-agent/etc/config.json
# Point to /var/log/cinematch.log

sudo systemctl start amazon-cloudwatch-agent
```

**Estimated Cost**: $5/month (5GB logs, 10 alarms)

---

## 💰 Total Cost Breakdown (Monthly)

| Service | Configuration | Cost |
|---------|--------------|------|
| **EC2 (t3.medium)** | 2 vCPU, 4GB RAM, always-on | $26.00 |
| **RDS (db.t3.micro)** | PostgreSQL, 20GB storage | $15.00 |
| **S3** | 5GB data storage | $0.50 |
| **Secrets Manager** | 1 secret | $0.40 |
| **CloudWatch** | 5GB logs, 10 alarms | $5.00 |
| **Data Transfer** | 100GB/month egress | $9.00 |
| **Total** | | **~$56/month** |

**Ways to reduce cost**:
- Use t3.small instead of t3.medium: Save $13/month (might be enough)
- Use AWS Free Tier (12 months): EC2 t2.micro FREE, RDS FREE, S3 5GB FREE
- **With Free Tier**: ~$10/month for first year!

---

## 🚀 Migration Steps (Local → AWS)

### **Day 1: Setup (2-3 hours)**

#### Step 1: Create EC2 Instance
```bash
# Launch EC2 instance from AWS Console
1. Choose Ubuntu 22.04 AMI
2. Select t3.medium instance type
3. Create security group (ports 80, 443, 22)
4. Generate SSH key pair
5. Launch instance
```

#### Step 2: Set Up RDS Database
```bash
# Create RDS instance from AWS Console
1. Choose PostgreSQL 15
2. Select db.t3.micro
3. Set master username/password
4. Create database "cinematch"
5. Note the endpoint URL
```

#### Step 3: Create S3 Bucket
```bash
# Create S3 bucket and upload data
aws s3 mb s3://cinematch-data
aws s3 sync data/processed/ s3://cinematch-data/processed/
```

#### Step 4: Store Secrets
```bash
# Create secret in Secrets Manager
aws secretsmanager create-secret \
  --name cinematch/prod \
  --secret-string '{"DB_HOST":"...","GROQ_API_KEY":"..."}'
```

#### Step 5: Deploy Application to EC2
```bash
# SSH into EC2 instance
ssh -i mykey.pem ubuntu@<ec2-public-ip>

# Install dependencies
sudo apt update
sudo apt install python3.11 python3-pip git nginx -y

# Clone your repository
git clone https://github.com/your-username/movie-recommender.git
cd movie-recommender

# Install Python packages
pip3 install -r requirements.txt

# Set up environment (load from Secrets Manager)
python3 scripts/load_secrets.py > .env

# Download data from S3 to local
aws s3 sync s3://cinematch-data/processed/ data/processed/

# Migrate SQLite → PostgreSQL
python3 scripts/migrate_to_postgres.py

# Run the application
uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers 2
```

#### Step 6: Set Up Nginx (optional, for HTTPS)
```bash
# Install SSL certificate (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com

# Configure Nginx reverse proxy
sudo nano /etc/nginx/sites-available/cinematch
```

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo nginx -t
sudo systemctl restart nginx
```

#### Step 7: Set Up Auto-Start
```bash
# Create systemd service to auto-start on reboot
sudo nano /etc/systemd/system/cinematch.service
```

```ini
[Unit]
Description=CineMatch FastAPI App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/movie-recommender
ExecStart=/usr/local/bin/uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cinematch
sudo systemctl start cinematch
sudo systemctl status cinematch
```

**Done! Your app is now live on AWS.** 🎉

---

## 🔐 Security Setup

### 1. **EC2 Security Group**
```yaml
Inbound Rules:
  - HTTP (80): 0.0.0.0/0 (allow public access)
  - HTTPS (443): 0.0.0.0/0 (allow public access)
  - SSH (22): YOUR_IP/32 (restrict to your IP only)

Outbound Rules:
  - All traffic: 0.0.0.0/0 (allow EC2 to access RDS, S3, internet)
```

### 2. **RDS Security Group**
```yaml
Inbound Rules:
  - PostgreSQL (5432): <EC2-security-group-id> (only EC2 can connect)
  
Outbound Rules:
  - None needed
```

### 3. **IAM Role for EC2**
```yaml
Role Name: CineMatch-EC2-Role

Policies:
  - AmazonS3ReadOnlyAccess (read Parquet files)
  - SecretsManagerReadWrite (read secrets)
  - CloudWatchAgentServerPolicy (send logs)
```

Attach this role to your EC2 instance so it can access S3 and Secrets Manager without hardcoded credentials.

---

## 📊 Performance & Scalability

### **Current Setup (Single EC2)**
- **Concurrent Users**: 50-100
- **API Response Time**: ~200ms
- **Uptime**: 99% (single instance)

### **When You Need to Scale** (Future)
If traffic grows beyond 100 concurrent users:

**Option 1: Vertical Scaling** (Easier)
- Upgrade EC2: t3.medium → t3.large ($52/month)
- Handles 200-300 concurrent users

**Option 2: Horizontal Scaling** (Better)
- Add Load Balancer (ALB): $16/month
- Run 2-3 EC2 instances behind ALB
- Auto-scaling based on CPU usage
- Handles 500+ concurrent users

---

## 📈 Monitoring Dashboard

### **CloudWatch Metrics to Track**

```yaml
Key Metrics:
  1. EC2 CPU Utilization
     - Normal: < 60%
     - Alert: > 80%
  
  2. EC2 Memory Utilization
     - Normal: < 70%
     - Alert: > 85%
  
  3. RDS CPU Utilization
     - Normal: < 50%
     - Alert: > 75%
  
  4. RDS Database Connections
     - Normal: < 50
     - Alert: > 80
  
  5. Application Error Rate
     - Normal: < 1%
     - Alert: > 5%
```

### **Alarms to Set**
```bash
# CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name cinematch-high-cpu \
  --metric-name CPUUtilization \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions <SNS-topic-ARN>

# Disk space alarm
aws cloudwatch put-metric-alarm \
  --alarm-name cinematch-low-disk \
  --metric-name FreeStorageSpace \
  --threshold 2000000000 \
  --comparison-operator LessThanThreshold
```

---

## 🔄 Backup & Recovery

### **Automated Backups**

```yaml
RDS Backups:
  - Automated daily snapshots: Enabled (7-day retention)
  - Backup window: 3:00 AM UTC
  - Recovery: Point-in-time restore (up to 7 days)

EC2 Snapshots:
  - Manual snapshots: Weekly (using AWS Backup)
  - Stores: AMI + EBS volume
  - Recovery: Launch new instance from AMI

S3 Versioning:
  - Enabled on cinematch-data bucket
  - Can restore deleted/overwritten files
```

### **Disaster Recovery**
If EC2 instance fails:
1. Launch new EC2 from latest AMI snapshot (15 minutes)
2. RDS automatically fails over to standby (if Multi-AZ enabled)
3. Update DNS to point to new EC2 IP
4. **Recovery Time Objective (RTO)**: < 30 minutes

---

## 🎯 Summary

### **What We're Using**
| Service | Purpose | Can't Live Without It? |
|---------|---------|----------------------|
| **EC2** | Run FastAPI app | ✅ YES - Need a server |
| **RDS** | Store user data | ✅ YES - Need a database |
| **S3** | Store data files | ✅ YES - Need file storage |
| **Secrets Manager** | Store API keys | ✅ YES - Security requirement |
| **CloudWatch** | Logs & monitoring | ✅ YES - Need visibility |

**That's it. Just 5 services. No over-engineering.**

### **What We're NOT Using** (and why)
| Service | Why Not? |
|---------|----------|
| Lambda | EC2 is simpler for our use case |
| API Gateway | FastAPI on EC2 is already an API |
| CloudFront | Not needed for small user base |
| SQS | No async tasks required yet |
| ElastiCache | App is fast enough without caching |
| Route 53 | Can use EC2 public IP directly |
| EventBridge | No scheduled jobs needed yet |

---

## ✅ Deployment Checklist

**Before Going Live:**
- [ ] EC2 instance running with Nginx
- [ ] RDS database created and migrated
- [ ] S3 bucket with processed data files
- [ ] Secrets stored in Secrets Manager
- [ ] CloudWatch alarms configured
- [ ] Security groups locked down
- [ ] SSL certificate installed (HTTPS)
- [ ] Auto-start service enabled
- [ ] Test all endpoints (signup, login, recommendations, chat)
- [ ] Load test with 50 concurrent users
- [ ] Backup strategy verified

**Monthly Maintenance:**
- [ ] Review CloudWatch logs for errors
- [ ] Check RDS backup status
- [ ] Update Python dependencies (security patches)
- [ ] Review AWS bill

---

## 📚 Resources

**AWS Console Links:**
- [EC2 Dashboard](https://console.aws.amazon.com/ec2/)
- [RDS Dashboard](https://console.aws.amazon.com/rds/)
- [S3 Dashboard](https://console.aws.amazon.com/s3/)
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/)

**Documentation:**
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [AWS EC2 User Guide](https://docs.aws.amazon.com/ec2/)
- [PostgreSQL on RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/)

---

**Document Version**: 2.0 (Simplified)  
**Last Updated**: January 2025  
**Architecture**: Right-sized for real-world deployment  
**Status**: Production-ready with 5 essential services

**Purpose**: Store user accounts, ratings, and preferences

**Why PostgreSQL?**
- ✅ Production-grade relational database
- ✅ ACID compliance (data integrity)
- ✅ Automated backups
- ✅ Multi-AZ for high availability
- ✅ Easy migration from SQLite

**Configuration**:
```yaml
RDS Instance:
  Engine: PostgreSQL 15
  Instance Class: db.t3.micro (20GB storage)
  Multi-AZ: Enabled (for production)
  Backup Retention: 7 days
  Encryption: Enabled (at rest)
  
Database Schema:
  tables:
    - users (id, username, email, password_hash, created_at)
    - user_genres (user_id, genre)
    - user_ratings (user_id, movie_id, rating, timestamp)
    - sessions (session_id, user_id, expires_at)
```

**Operations**:
- `INSERT INTO users` - Create new accounts
- `SELECT * FROM users WHERE username=?` - Login validation
- `INSERT INTO user_genres` - Save genre preferences
- `SELECT genres FROM user_genres WHERE user_id=?` - Load preferences
- `INSERT INTO user_ratings` - Record movie ratings

**Migration from SQLite**:
```bash
# Export SQLite data
sqlite3 data/users.db .dump > users_export.sql

# Import to PostgreSQL (with modifications)
psql -h <rds-endpoint> -U admin -d cinematch -f users_export.sql
```

**Estimated Cost**: $15-30/month (t3.micro instance)

---

### 4. **Amazon S3** (Object Storage)

**Purpose**: Store processed data, ML models, and static assets

**Buckets**:

#### **A. cinematch-data** (Private - Data Lake)
```
s3://cinematch-data/
├── raw/
│   ├── movies.csv
│   └── ratings.csv
├── processed/
│   ├── movies.parquet
│   ├── ratings.parquet
│   ├── genre_matrix.parquet
│   └── user_movie_matrix.parquet
├── models/
│   ├── content_model.pkl
│   └── collaborative_model.pkl
└── logs/
    └── recommendations_{date}.json
```

**Operations**:
- Lambda reads Parquet files on cold start
- Lambda caches matrices in memory (warm start optimization)
- Periodic updates via scheduled Lambda (nightly re-training)
- Versioning enabled for model rollback

#### **B. cinematch-frontend** (Public - Static Website)
```
s3://cinematch-frontend/
├── index.html
├── favicon.ico
└── assets/
    └── logo.png
```

**Static Website Hosting**:
- Served via CloudFront CDN
- HTTPS enabled (SSL certificate from ACM)
- Gzip compression enabled

**Estimated Cost**: $1-5/month (1GB data + requests)

---

### 5. **Amazon CloudFront** (CDN)

**Purpose**: Global content delivery and caching

**Benefits**:
- ✅ Low latency worldwide (edge locations)
- ✅ DDoS protection (AWS Shield)
- ✅ SSL/TLS termination
- ✅ Caching static assets (reduce S3 costs)
- ✅ Custom domain support

**Configuration**:
```yaml
CloudFront Distribution:
  Origins:
    - S3: cinematch-frontend (static files)
    - API Gateway: api.cinematch.com (API)
  
  Cache Behaviors:
    - Path: /          → S3 (cache 24 hours)
    - Path: /assets/*  → S3 (cache 7 days)
    - Path: /api/*     → API Gateway (no cache)
  
  Security:
    - SSL Certificate: *.cinematch.com (ACM)
    - WAF: Enabled (block SQL injection, XSS)
    - Geo-restriction: None
```

**Estimated Cost**: $10-20/month (100GB data transfer)

---

### 6. **AWS Secrets Manager** (Secrets Storage)

**Purpose**: Securely store API keys, database credentials, and JWT secrets

**Secrets Stored**:
```yaml
Secrets:
  - cinematch/db-credentials
      username: admin
      password: {encrypted}
      host: cinematch-db.xyz.rds.amazonaws.com
      port: 5432
      
  - cinematch/groq-api-key
      key: gsk_xxxxxxxxxxxxx
      
  - cinematch/jwt-secret
      secret: {256-bit random key}
```

**Operations**:
- Lambda retrieves secrets at runtime
- Automatic rotation (90 days)
- Encrypted with AWS KMS
- Audit logging via CloudTrail

**Estimated Cost**: $0.40/secret/month

---

### 7. **Amazon CloudWatch** (Monitoring & Logging)

**Purpose**: Application monitoring, logging, and alerting

**Metrics Tracked**:
```yaml
Lambda Metrics:
  - Invocations (requests/second)
  - Duration (average response time)
  - Errors (4xx, 5xx counts)
  - Throttles (rate limit hits)
  
API Gateway Metrics:
  - Request count
  - Latency (p50, p90, p99)
  - 4xx/5xx error rates
  
RDS Metrics:
  - CPU utilization
  - Database connections
  - Read/Write IOPS
  - Storage space
```

**Logs**:
```
/aws/lambda/cineMatch-recommender
  └── 2024/01/15
      └── [START] Request: 5a3b2c1d
      └── [INFO] Loading models from S3...
      └── [INFO] Generated 10 recommendations for user 123
      └── [END] Duration: 1250ms Memory: 512MB

/aws/lambda/cineMatch-chatbot
  └── 2024/01/15
      └── [INFO] User query: "Tell me about Inception"
      └── [INFO] Groq API latency: 850ms
      └── [INFO] Response sent (245 tokens)
```

**Alarms**:
- High error rate (>5%) → SNS notification
- High latency (>3s p99) → SNS notification
- RDS CPU >80% → Auto-scaling trigger
- Lambda throttles → Increase concurrency limit

**Estimated Cost**: $5-10/month (10GB logs)

---

### 8. **Amazon SQS** (Message Queue)

**Purpose**: Asynchronous task processing

**Use Cases**:
```yaml
Queue: cineMatch-recommendation-jobs
  Purpose: Background re-computation of recommendations
  
Operations:
  1. User rates a movie → Event sent to SQS
  2. Lambda worker picks up job
  3. Re-computes personalized recommendations
  4. Updates cache in S3/RDS
  5. Sends completion notification

Queue: cineMatch-model-training
  Purpose: Periodic ML model retraining
  
Operations:
  1. CloudWatch Event (daily at 2 AM)
  2. Triggers Lambda → Sends job to SQS
  3. Worker Lambda trains new models
  4. Uploads to S3 with versioning
  5. Notifies via SNS on completion
```

**Estimated Cost**: $0.40/million requests (free tier: 1M/month)

---

### 9. **Amazon EventBridge** (Event Scheduling)

**Purpose**: Trigger periodic tasks and automation

**Scheduled Events**:
```yaml
Rule: DailyModelRetraining
  Schedule: cron(0 2 * * ? *)  # 2 AM daily
  Target: Lambda (model-training)
  
Rule: HourlyStatsAggregation
  Schedule: rate(1 hour)
  Target: Lambda (aggregate-stats)
  
Rule: WeeklyBackup
  Schedule: cron(0 3 ? * SUN *)  # Sunday 3 AM
  Target: Lambda (backup-to-glacier)
```

**Estimated Cost**: Free (14 rules included)

---

### 10. **AWS Certificate Manager (ACM)** (SSL/TLS)

**Purpose**: Free SSL certificates for HTTPS

**Certificates**:
- `cinematch.com`
- `*.cinematch.com` (wildcard)
- `api.cinematch.com`

**Operations**:
- Auto-renewal before expiry
- CloudFront integration
- API Gateway custom domain

**Estimated Cost**: **FREE**

---

### 11. **Amazon Route 53** (DNS Management)

**Purpose**: Domain name management and routing

**DNS Records**:
```yaml
cinematch.com
  Type: A
  Alias: CloudFront distribution
  
api.cinematch.com
  Type: A
  Alias: API Gateway custom domain
  
www.cinematch.com
  Type: CNAME
  Value: cinematch.com
```

**Estimated Cost**: $0.50/hosted zone + $0.40/million queries

---

## 🔄 Data Flow & Operations

### 1. **User Signup Flow**
```
User Browser
    → CloudFront (CDN)
    → API Gateway (/auth/signup)
    → Lambda (Auth)
    → RDS (INSERT user)
    → Secrets Manager (JWT secret)
    ← JWT Token
    ← Response to user
```

### 2. **Personalized Recommendations Flow**
```
User Browser (with JWT)
    → CloudFront
    → API Gateway (/me/recommend)
    → Lambda@Edge (verify JWT)
    → Lambda (Recommender)
    → RDS (get user genres)
    → S3 (load Parquet data + models)
    → Compute recommendations (in-memory)
    ← JSON response
    → CloudWatch (log metrics)
```

### 3. **Chatbot Conversation Flow**
```
User message
    → API Gateway (/chat)
    → Lambda (Chatbot)
    → S3 (search movie dataset)
    → Groq API (external, AI inference)
    ← AI response
    → CloudWatch (log conversation)
    ← Response to user
```

### 4. **Mood-Based Recommendations Flow**
```
User selects mood
    → API Gateway (/moods/intense)
    → Lambda (Recommender)
    → S3 (load data)
    → Compute base recommendations
    → Apply mood boost (+0.25 to matching genres)
    → Re-rank and sort
    ← Top N recommendations
```

---

## 📊 Deployment Pipeline (CI/CD)

### **AWS CodePipeline + CodeBuild**

```yaml
Pipeline: cineMatch-deployment

Stages:
  1. Source
     - GitHub repository (main branch)
     - Webhook on push
     
  2. Build
     - CodeBuild project
     - Install Python dependencies
     - Run tests (pytest)
     - Package Lambda functions (zip)
     - Build Docker image (optional)
     
  3. Test
     - Deploy to staging environment
     - Run integration tests
     - Load testing (Locust or Artillery)
     
  4. Manual Approval
     - Slack notification
     - Requires team lead approval
     
  5. Deploy to Production
     - Update Lambda functions
     - Update API Gateway
     - Invalidate CloudFront cache
     - Run smoke tests
     
  6. Notify
     - SNS notification (success/failure)
     - Slack alert
```

---

## 💰 Cost Breakdown (Monthly Estimates)

### **Moderate Traffic Scenario** (10,000 users, 100,000 requests/day)

| Service | Usage | Cost |
|---------|-------|------|
| **API Gateway** | 3M requests | $10.50 |
| **Lambda** | 3M invocations, 512MB avg | $15.00 |
| **RDS PostgreSQL** | db.t3.micro, 20GB | $25.00 |
| **S3 Storage** | 5GB data + requests | $2.00 |
| **CloudFront** | 100GB transfer | $15.00 |
| **CloudWatch** | 10GB logs, 20 alarms | $8.00 |
| **Secrets Manager** | 4 secrets | $1.60 |
| **Route 53** | 1 hosted zone | $0.50 |
| **SQS** | 1M messages | $0.40 |
| **ACM** | SSL certificates | FREE |
| **EventBridge** | 10 rules | FREE |
| **Total** | | **~$78/month** |

### **High Traffic Scenario** (100,000 users, 1M requests/day)

| Service | Cost Increase |
|---------|---------------|
| API Gateway | $105 |
| Lambda | $60 |
| RDS (scaled to db.t3.small) | $50 |
| CloudFront | $40 |
| **Total** | **~$280/month** |

**Cost Optimization Tips**:
- Use Reserved Capacity for RDS (save 30-40%)
- Enable Lambda caching (reduce S3 reads)
- Compress API responses (reduce data transfer)
- Set intelligent S3 lifecycle policies (move old data to Glacier)

---

## 🔐 Security Implementation

### **1. Authentication & Authorization**
```yaml
JWT Token Flow:
  - User logs in → Lambda generates JWT
  - Token includes: user_id, username, expiry
  - Token signed with secret from Secrets Manager
  - API Gateway validates JWT on every request
  - Lambda@Edge pre-validates at edge locations

Security Headers:
  - Strict-Transport-Security: max-age=31536000
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Content-Security-Policy: default-src 'self'
```

### **2. Network Security**
```yaml
VPC Configuration:
  - Lambda in private subnets (no direct internet)
  - RDS in isolated private subnet
  - NAT Gateway for outbound Lambda traffic
  
Security Groups:
  - Lambda → RDS: Port 5432 only
  - API Gateway → Lambda: HTTPS only
  - CloudFront → S3: Origin Access Identity (OAI)
```

### **3. Data Protection**
```yaml
Encryption:
  - At Rest: All S3 buckets (AES-256)
  - At Rest: RDS (KMS encryption)
  - In Transit: TLS 1.2+ enforced
  - Secrets: AWS KMS encryption

Backup Strategy:
  - RDS: Automated daily snapshots (7-day retention)
  - S3: Versioning enabled
  - Point-in-time recovery for RDS
```

---

## 📈 Scalability & Performance

### **Auto-Scaling Configuration**

```yaml
Lambda Concurrency:
  - Reserved: 50 (guaranteed capacity)
  - Burst: 1000 (spike handling)
  - Provisioned concurrency: 10 (eliminate cold starts)

RDS Auto-Scaling:
  - Min Capacity: db.t3.micro
  - Max Capacity: db.t3.large
  - Trigger: CPU > 75% for 5 minutes
  - Scale-down: CPU < 30% for 15 minutes

API Gateway Throttling:
  - Burst: 2000 requests
  - Rate: 1000 requests/second
  - Per-user limit: 100 requests/minute
```

### **Caching Strategy**

```yaml
CloudFront Cache:
  - Static assets: 7 days
  - API responses: No cache (dynamic data)
  
Lambda Internal Cache:
  - Parquet data: Loaded once per container lifetime
  - ML models: Cached in /tmp directory (warm starts)
  
Application-Level Cache:
  - ElastiCache Redis (optional future enhancement)
  - Cache popular recommendations (TTL: 1 hour)
```

---

## 🚀 Migration Steps (Local → AWS)

### **Phase 1: Data Migration** (Day 1)
1. **Upload datasets to S3**
   ```bash
   aws s3 sync data/processed/ s3://cinematch-data/processed/
   ```
2. **Migrate SQLite to RDS**
   ```bash
   python scripts/migrate_sqlite_to_postgres.py
   ```

### **Phase 2: Lambda Deployment** (Day 1-2)
1. **Package Lambda functions**
   ```bash
   cd lambda/recommender
   pip install -r requirements.txt -t .
   zip -r function.zip .
   ```
2. **Deploy via AWS CLI**
   ```bash
   aws lambda create-function \
     --function-name cineMatch-recommender \
     --runtime python3.11 \
     --zip-file fileb://function.zip
   ```

### **Phase 3: API Gateway Setup** (Day 2)
1. Create REST API
2. Define resources and methods
3. Integrate with Lambda functions
4. Deploy to production stage

### **Phase 4: Frontend Deployment** (Day 2)
1. Update API endpoint URLs in frontend
2. Upload to S3 bucket
3. Configure CloudFront distribution
4. Set up custom domain

### **Phase 5: Testing & Go-Live** (Day 3)
1. Run end-to-end tests
2. Load testing (simulate 1000 concurrent users)
3. Monitor CloudWatch for errors
4. Switch DNS to production

---

## 📝 Monitoring & Maintenance

### **CloudWatch Dashboards**

```yaml
Dashboard: CineMatch-Production

Widgets:
  - Lambda Invocations (line chart, 1-hour window)
  - API Gateway Latency (heatmap, p50/p90/p99)
  - RDS Connections (gauge)
  - Error Rate (alarm status)
  - Cost Explorer (monthly spend)
```

### **Alerting Rules**

```yaml
Alarms:
  Critical:
    - Lambda error rate > 5% (5 minutes)
      → SNS → Slack → On-call engineer
    
    - RDS CPU > 90% (10 minutes)
      → Auto-scale + SNS alert
    
    - API Gateway 5xx > 1% (5 minutes)
      → Page on-call team
  
  Warning:
    - Lambda duration > 2s (p95)
      → Slack notification
    
    - CloudFront cache hit rate < 60%
      → Investigate cache configuration
```

---

## 🎯 Performance Benchmarks (Expected)

| Metric | Local | AWS (Optimized) |
|--------|-------|-----------------|
| **API Response Time (p50)** | 250ms | 180ms |
| **API Response Time (p99)** | 800ms | 450ms |
| **Recommendation Latency** | 300ms | 200ms |
| **Chatbot Response Time** | 1.2s | 900ms |
| **Concurrent Users** | 10 | 10,000+ |
| **Uptime** | 95% | 99.9% |
| **Cold Start (Lambda)** | N/A | 1.5s → 150ms (provisioned) |

---

## 🔮 Future Enhancements (AWS-Enabled)

### **1. Real-Time Recommendations**
- **AWS Kinesis Data Streams**: Process user interactions in real-time
- **Amazon EMR**: Spark jobs for large-scale collaborative filtering
- **DynamoDB**: Store pre-computed recommendations for instant retrieval

### **2. Machine Learning Pipeline**
- **AWS SageMaker**: Train deep learning models (neural collaborative filtering)
- **SageMaker Pipelines**: Automated MLOps workflow
- **Model Registry**: Version control for ML models

### **3. Advanced Analytics**
- **Amazon Athena**: SQL queries on S3 data lake
- **Amazon QuickSight**: Business intelligence dashboards
- **AWS Glue**: ETL pipelines for data processing

### **4. Global Expansion**
- **Multi-Region Deployment**: US-East, EU-West, Asia-Pacific
- **DynamoDB Global Tables**: Replicate user data across regions
- **Route 53 Latency Routing**: Route users to nearest region

---

## 📚 References & Documentation

### **AWS Documentation Links**
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [API Gateway Developer Guide](https://docs.aws.amazon.com/apigateway/)
- [RDS PostgreSQL Guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/)
- [CloudFront Distribution Setup](https://docs.aws.amazon.com/cloudfront/)

### **Internal Documentation**
- `README.md` - Local setup and quick start
- `PROJECT_DOCUMENTATION.md` - Complete project overview
- `QUICKSTART.md` - Installation and testing guide
- `PHASE2_COMPLETE.md` - Phase 2 features documentation

---

## ✅ Conclusion

CineMatch is architected with **AWS-native design principles** from day one:

✅ **Serverless-first**: No server management overhead  
✅ **Stateless design**: JWT authentication works seamlessly with Lambda  
✅ **Data lake architecture**: S3 stores processed Parquet files  
✅ **Managed databases**: RDS eliminates database administration  
✅ **Global CDN**: CloudFront ensures low latency worldwide  
✅ **Security-first**: Secrets Manager, KMS encryption, WAF protection  
✅ **Cost-optimized**: Pay-per-use model, auto-scaling  
✅ **Highly available**: Multi-AZ deployment, 99.9% uptime SLA  

**Migration Complexity**: ⭐⭐ (Low - Minimal code changes required)  
**Estimated Timeline**: 2-3 days for full production deployment  
**Monthly Cost**: $78-280 depending on traffic  

The system is **production-ready** and can scale from 10 to 100,000+ users with zero architectural changes.

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Author**: CineMatch Development Team  
**Status**: Ready for AWS Deployment
