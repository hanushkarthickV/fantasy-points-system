# Future Exploration — OTP Auth & AWS Scheduled Jobs

## 7.1 OTP-based Authentication (Phone/Email)

### Can we add it?
**Yes**, absolutely. Here are the options:

### Option A: Supabase Auth (Recommended — easiest)
Supabase has built-in email OTP (magic link) and phone OTP authentication:

1. **Enable in Supabase Dashboard**: Settings → Auth → Email → Enable "Magic Link"
2. **For Phone OTP**: Settings → Auth → Phone → Enable, configure Twilio
3. **Frontend**: Use `@supabase/supabase-js` client library
4. **Backend**: Verify Supabase JWT tokens instead of rolling our own

**Pros**: No custom code, battle-tested, free tier includes email OTP
**Cons**: Tied to Supabase ecosystem; phone OTP needs Twilio ($)

### Option B: Custom Email OTP (using SMTP)
1. Generate a 6-digit OTP, store in Redis/DB with 5-min expiry
2. Send via email (use Gmail SMTP, SendGrid, or Resend)
3. User enters OTP → verify against stored value → issue JWT

**Implementation sketch**:
```python
# POST /api/v2/auth/send-otp
@router_auth.post("/send-otp")
async def send_otp(email: str, db: Session = Depends(get_db)):
    otp = str(random.randint(100000, 999999))
    # Store in DB with expiry
    db.add(OTPRecord(email=email, otp=otp, expires_at=now+5min))
    db.commit()
    # Send email
    send_email(to=email, subject="Your OTP", body=f"Your code: {otp}")
    return {"message": "OTP sent"}

# POST /api/v2/auth/verify-otp
@router_auth.post("/verify-otp")
async def verify_otp(email: str, otp: str, db: Session = Depends(get_db)):
    record = db.query(OTPRecord).filter_by(email=email, otp=otp).first()
    if not record or record.expires_at < now:
        raise HTTPException(401, "Invalid or expired OTP")
    # Issue JWT
    token = jwt.encode({"sub": email}, SECRET, algorithm="HS256")
    return {"token": token}
```

**Pros**: Full control, works with any email provider
**Cons**: Need SMTP setup, more code to maintain

### Option C: Phone OTP via Twilio
Same as Option B but uses Twilio Verify API:
```python
from twilio.rest import Client
client = Client(TWILIO_SID, TWILIO_TOKEN)
# Send
client.verify.v2.services(SERVICE_SID).verifications.create(to=phone, channel="sms")
# Verify
check = client.verify.v2.services(SERVICE_SID).verification_checks.create(to=phone, code=otp)
```

**Cost**: ~$0.05 per SMS (Twilio), free trial has $15 credit

### Recommendation
Start with **Supabase Auth** (Option A) for email OTP — it's free and requires zero custom code.
Add phone OTP later via Twilio if needed.

---

## 7.2 AWS Scheduled Job for Extraction Queue

### Is it possible?
**Yes**. Instead of the in-process worker thread, you can offload extraction to AWS.

### Architecture

```
[Render Web App]  →  writes to extraction_queue table
                           ↓
[AWS EventBridge]  →  triggers Lambda every 1 minute
                           ↓
[AWS Lambda]       →  reads pending jobs from Supabase DB
                    →  runs extraction (or triggers ECS/Fargate task)
                    →  updates match row with results
```

### Option A: AWS Lambda + EventBridge (Simplest)
1. **EventBridge Rule**: Cron `rate(1 minute)` triggers Lambda
2. **Lambda function**: Connects to Supabase PostgreSQL, checks for pending jobs
3. **Problem**: Lambda has 15-min timeout and limited resources.
   Selenium is heavy (~500MB+). Lambda might not be ideal for Selenium.

### Option B: AWS Lambda → ECS Fargate Task (Better)
1. **Lambda** (triggered by EventBridge) checks for pending jobs
2. If found, **launches an ECS Fargate task** (Docker container with Chrome)
3. Fargate task runs the extraction, writes results to DB, then stops
4. **Cost**: Pay only when tasks run (~$0.04/hour for 1 vCPU)

### Option C: AWS Step Functions (Most robust)
1. Step Function triggered by EventBridge or SQS
2. State machine: Check Queue → Start Extraction → Wait → Save Results
3. Built-in retry, error handling, and observability

### Is this the best approach?
**For your current scale (1-2 matches/day), the in-process worker thread is sufficient.**
AWS becomes valuable when:
- You have many concurrent users
- Extraction takes >30s and blocks the web server
- You want the web server to stay cold (save money) while extraction runs independently
- You need better observability (CloudWatch logs, X-Ray traces)

### Implementation Steps (if you decide to go with AWS)
1. Create a Docker image with Chrome + your extraction code
2. Push to AWS ECR (Elastic Container Registry)
3. Create an ECS Fargate task definition
4. Create a Lambda function that:
   - Connects to Supabase DB
   - Checks `extraction_queue` for `pending` jobs
   - If found, runs `ecs.run_task()` with the match_id as an env var
5. Create an EventBridge rule: `rate(1 minute)` → triggers the Lambda
6. In the Fargate task:
   - Read match_id from env
   - Connect to Supabase DB
   - Run extraction + points calculation
   - Update match row
   - Exit (container stops, billing stops)

### Estimated Cost
- EventBridge: Free (first 14M invocations/month)
- Lambda: Free (first 1M invocations/month)
- Fargate: ~$0.04/hour per task, ~30s per match = ~$0.0003/match
- **Total**: Practically free for IPL season (~70 matches)

### Recommendation
**Keep the in-process worker for now.** It's simple, works, and costs nothing.
Move to AWS Fargate only if you need to scale beyond a single Render instance
or want the web server to be completely stateless.
