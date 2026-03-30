
#!/bin/bash
# Start script for the Innovation game frontend

echo "Starting Innovation frontend..."

# Function to kill process on port
kill_port() {
    local port=$1
    echo "Checking for existing processes on port $port..."

    # Find and kill processes on the specified port
    if lsof -ti:$port > /dev/null 2>&1; then
        echo "Found existing process on port $port"
        echo "Stopping existing process..."
        lsof -ti:$port | xargs kill -9 2>/dev/null
        echo "Process stopped."
        sleep 1
    fi
}

# Kill any existing process on port 3000
kill_port 3000

# Change to frontend directory
cd "$(dirname "$0")/frontend" || exit 1

# Check if node_modules exists, if not install dependencies
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

echo "Starting React development server on http://localhost:3000"
echo "Press Ctrl+C to stop the server"

# Workaround for Rollup native binary issues on some Node versions
export ROLLUP_SKIP_NATIVE=1

# Start the development server (align with docs: use npm run dev)
# Force IPv4 localhost binding to avoid permission issues on ::1
npm run dev -- --host 127.0.0.1 --port 3000
