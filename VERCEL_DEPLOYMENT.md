# Vercel Deployment Guide for DeepAir Project

## 🔴 **CRITICAL ISSUE: Architectural Incompatibility**

### The Problem

Your Flask application (`dashboard.py`) is **not compatible** with Vercel's serverless architecture. Here's why:

1. **Long-Running Processes**: Your app uses `threading.Thread` with a sensor loop that runs continuously. Vercel serverless functions are **stateless** and **short-lived** (max 10 seconds for free tier, 60 seconds for Pro).

2. **In-Memory State**: Your app stores data in Python `deque` objects (`pm25_buf`, `pm10_buf`, `ts_buf`). Serverless functions don't maintain state between invocations - each request spawns a new function instance.

3. **Hardware Access**: Your app directly accesses COM3 serial port (`SDS011(port=PORT)`). Vercel runs in cloud containers with no access to your local hardware.

4. **Missing Configuration**: Vercel needs specific configuration files (`vercel.json`) and serverless function structure (`api/` directory) to understand how to route requests.

---

## ✅ **Solution Options**

### **Option A: Convert to Serverless Architecture (Recommended for Vercel)**

This requires significant architectural changes:

1. **External State Storage**: Replace in-memory buffers with:
   - **Vercel KV** (Redis-compatible, recommended)
   - **Database** (PostgreSQL, MongoDB)
   - **File storage** (for simple demos)

2. **Separate Sensor Service**: Run the sensor reader on a separate service:
   - **Raspberry Pi** or local machine
   - **Railway/Render** (can run long processes)
   - **AWS EC2** or similar VPS

3. **API Gateway Pattern**: The sensor service writes to storage, Vercel functions read from it.

**Files Created:**
- `api/live.py` - Serverless function skeleton (needs state storage implementation)
- `vercel.json` - Vercel routing configuration
- Updated frontend to use relative API paths

**What Still Needs Work:**
- Implement actual data fetching from external storage in `api/live.py`
- Set up sensor service that writes to your chosen storage
- Configure environment variables for storage credentials

---

### **Option B: Use Alternative Hosting (Easier, Recommended)**

For your current Flask architecture, these platforms are better suited:

#### **1. Railway** (Recommended)
- ✅ Supports long-running processes
- ✅ Easy Flask deployment
- ✅ Free tier available
- ✅ Can handle background threads

**Deployment:**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

#### **2. Render**
- ✅ Free tier for web services
- ✅ Supports Flask
- ✅ Can run background processes

**Deployment:**
- Connect GitHub repo
- Set build command: `pip install -r requirements.txt`
- Set start command: `python dashboard.py`

#### **3. Heroku**
- ✅ Well-documented Flask support
- ⚠️ Requires credit card for free tier
- ⚠️ More complex setup

#### **4. PythonAnywhere**
- ✅ Designed for Python apps
- ✅ Free tier available
- ✅ Easy Flask deployment

---

## 📋 **What Was Fixed**

### 1. Created `vercel.json`
This tells Vercel:
- How to route `/api/*` requests to Python serverless functions
- How to serve your frontend static files
- Which build tools to use (`@vercel/python`)

### 2. Created `api/live.py`
A skeleton serverless function that:
- Matches your Flask endpoint structure
- Includes CORS headers
- Has placeholder for external state storage

### 3. Updated Frontend
Changed hardcoded `http://localhost:5000/api/live` to:
- Use relative path `/api/live` for production
- Fallback to localhost for local development

---

## 🚨 **Why NOT_FOUND Error Occurred**

### Root Cause Analysis

**What Vercel Expected:**
- Serverless functions in `api/` directory
- Static files in `public/` or configured directory
- `vercel.json` configuration file

**What You Had:**
- Flask app with `app.run()` (long-running server)
- No `vercel.json` configuration
- No `api/` directory structure
- Frontend calling non-existent endpoints

**What Happened:**
1. You deployed to Vercel without proper configuration
2. Vercel tried to auto-detect your project type
3. It couldn't find expected files/routes
4. All requests returned `NOT_FOUND` because Vercel didn't know how to handle them

---

## 🎓 **Understanding Serverless Architecture**

### Traditional Server (Your Flask App)
```
┌─────────────────┐
│  Flask Server   │
│  (Always On)    │
│                 │
│  - Threads      │
│  - Memory State │
│  - Port Binding │
└─────────────────┘
```

### Serverless Functions (Vercel)
```
Request 1 → Function Instance 1 → Response → Dies
Request 2 → Function Instance 2 → Response → Dies
Request 3 → Function Instance 3 → Response → Dies
```

**Key Differences:**
- **State**: Serverless functions are stateless (no memory between requests)
- **Lifetime**: Functions live only for the request duration
- **Scaling**: Auto-scales to zero when not in use
- **Cost**: Pay per invocation, not per uptime

### Why This Matters for Your App

Your sensor loop needs to:
- ✅ Run continuously (not possible in serverless)
- ✅ Maintain state between reads (requires external storage)
- ✅ Access hardware (requires separate service)

---

## 🔍 **Warning Signs to Watch For**

### Code Patterns That Won't Work on Vercel:

1. **Background Threads**
   ```python
   # ❌ Won't work
   threading.Thread(target=sensor_loop, daemon=True)
   ```

2. **In-Memory State**
   ```python
   # ❌ Lost between requests
   pm25_buf = deque(maxlen=WINDOW_SIZE)
   ```

3. **Long-Running Loops**
   ```python
   # ❌ Function times out
   while True:
       sensor.read()
   ```

4. **Hardware Access**
   ```python
   # ❌ No COM ports in cloud
   sensor = SDS011(port="COM3")
   ```

### What to Use Instead:

1. **External Storage**
   ```python
   # ✅ Works
   redis_client.set('pm25', value)
   ```

2. **Separate Service**
   ```python
   # ✅ Sensor runs on Raspberry Pi
   # ✅ Writes to database/Redis
   # ✅ Vercel reads from storage
   ```

3. **Event-Driven**
   ```python
   # ✅ Function triggered by webhook/API
   def handler(request):
       data = fetch_from_storage()
       return jsonify(data)
   ```

---

## 🛠️ **Next Steps**

### If Staying with Vercel:

1. **Set up external storage:**
   ```bash
   # Install Vercel KV
   vercel kv create
   ```

2. **Update `api/live.py`** to fetch from storage:
   ```python
   from vercel_kv import kv
   data = kv.get('air_quality_data')
   ```

3. **Create sensor service** (separate deployment):
   - Runs on local machine/Raspberry Pi
   - Reads sensor data
   - Writes to Vercel KV/database
   - Runs continuously

4. **Deploy:**
   ```bash
   vercel
   ```

### If Switching to Railway/Render:

1. **Keep your current Flask app** (no changes needed!)
2. **Create `Procfile`** (for Railway/Render):
   ```
   web: python dashboard.py
   ```
3. **Deploy** using their platform-specific commands

---

## 📚 **Key Concepts**

### 1. **Stateless vs Stateful**
- **Stateless**: Each request is independent (serverless)
- **Stateful**: Server maintains data between requests (traditional)

### 2. **Cold Starts**
- Serverless functions "wake up" on first request
- Can add 1-3 seconds latency
- Your sensor loop would cause constant cold starts

### 3. **Function Timeouts**
- Vercel Free: 10 seconds max
- Vercel Pro: 60 seconds max
- Your sensor loop runs forever → timeout

### 4. **Request/Response Model**
- Serverless functions receive HTTP request
- Process and return response
- Cannot maintain open connections or background processes

---

## 💡 **Recommendation**

**For your use case, I recommend Railway or Render** because:
- ✅ Your Flask app works as-is
- ✅ Supports long-running processes
- ✅ Easier deployment
- ✅ Better suited for IoT/hardware projects

**Use Vercel if:**
- You're willing to refactor to serverless architecture
- You want to separate sensor service from API
- You need global edge distribution
- You're building a scalable API

---

## 🆘 **Troubleshooting**

### Still Getting NOT_FOUND?

1. **Check `vercel.json` exists** in project root
2. **Verify `api/` directory structure**:
   ```
   api/
     __init__.py
     live.py
   ```
3. **Check build logs** in Vercel dashboard
4. **Verify routes** match your frontend calls
5. **Test locally** with `vercel dev`

### Common Mistakes:

- ❌ Forgetting to update frontend API URLs
- ❌ Missing `__init__.py` in `api/` directory
- ❌ Incorrect route patterns in `vercel.json`
- ❌ Trying to use Flask's `app.run()` in serverless function

---

## 📖 **Further Reading**

- [Vercel Python Runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel KV Documentation](https://vercel.com/docs/storage/vercel-kv)
- [Serverless Architecture Patterns](https://aws.amazon.com/lambda/serverless-architectures-learn-more/)
- [Railway Flask Deployment](https://docs.railway.app/guides/flask)

