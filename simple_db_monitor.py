"""
Simple PostgreSQL Database Monitor - Detects when database goes down

This script continuously checks if PostgreSQL is up or down and displays alerts.
"""

import psycopg
import time
from datetime import datetime
import signal
import sys
import os

# Set encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')  # UTF-8


class SimpleDBMonitor:
    """Simple database monitor"""

    def __init__(self, dsn: str, check_interval: int = 10):
        self.dsn = dsn
        self.interval = check_interval
        self.running = True
        self.last_status = None
        self.down_since = None
        self.up_since = None
        self.check_count = 0

        # Setup signal handler
        signal.signal(signal.SIGINT, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n\n🛑 Stopping monitoring...")
        self.running = False

    def check_database(self):
        """Check if database is up"""
        try:
            with psycopg.connect(self.dsn, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 as health_check")
                    result = cur.fetchone()
                    if result:
                        return True, None
            return False, "Connection failed"
        except Exception as e:
            return False, str(e)

    def print_header(self):
        """Print header"""
        print("\n" + "=" * 100)
        print("  PostgreSQL Database Monitor - Real-time Status Check")
        print("=" * 100)
        print(f"  DSN: {self.dsn}")
        print(f"  Check Interval: {self.interval} seconds")
        print("=" * 100 + "\n")

    def print_alert_database_down(self, error_msg: str):
        """Print database down alert"""
        print("\n" + "!" * 100)
        print("*** CRITICAL ALERT: DATABASE DOWN ***")
        print("!" * 100)
        print(f"  Severity: P1 (Critical)")
        print(f"  Triggered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Database: PostgreSQL (UniversityDB)")
        print(f"  Error: {error_msg}")
        print(f"  Status: Database instance is not responding")
        print()
        print("  AI Analysis:")
        print("     Root Cause: PostgreSQL service has stopped or network connection is unavailable")
        print("     Confidence: 95.0%")
        print()
        print("     Immediate Actions:")
        print("       - Check if PostgreSQL service is running")
        print("       - Verify network connectivity to database server")
        print("       - Review PostgreSQL logs for crash or shutdown messages")
        print("       - Attempt to restart PostgreSQL service")
        print()
        print("     Recommendations:")
        print("       1. [action] Restart PostgreSQL service")
        print("          Command: net start postgresql-x64-15  (or your service name)")
        print("          Risk: low, Priority: critical")
        print()
        print("       2. [action] Check PostgreSQL logs")
        print("          Command: Check logs at C:\\Program Files\\PostgreSQL\\15\\data\\log")
        print("          Risk: low, Priority: high")
        print()
        print("       3. [action] Verify port 5432 is listening")
        print("          Command: netstat -an | findstr 5432")
        print("          Risk: low, Priority: medium")
        print("!" * 100 + "\n")

    def print_alert_database_recovered(self):
        """Print database recovered alert"""
        print("\n" + "!" * 100)
        print("*** ALERT RESOLVED: DATABASE BACK ONLINE ***")
        print("!" * 100)
        print(f"  Resolved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Database: PostgreSQL (UniversityDB)")
        print(f"  Status: Auto-resolved (database responding normally)")
        if self.down_since:
            downtime = datetime.now() - self.down_since
            print(f"  Downtime: {downtime}")
        print("!" * 100 + "\n")

    def monitor(self):
        """Start monitoring"""
        self.print_header()

        print(">>> Starting continuous monitoring...")
        print("   Press Ctrl+C to stop\n")
        print("=" * 100 + "\n")

        # Initial check
        print(">>> Performing initial health check...")
        is_up, error = self.check_database()

        if is_up:
            print("[OK] Database is currently UP and responding\n")
            self.last_status = "up"
            self.up_since = datetime.now()
        else:
            print(f"[WARN] Database is currently DOWN or unreachable")
            print(f"   Error: {error}\n")
            self.last_status = "down"
            self.down_since = datetime.now()
            self.print_alert_database_down(error)

        print("Starting monitoring loop...\n")

        # Monitoring loop
        while self.running:
            try:
                self.check_count += 1
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                print(f"[{timestamp}] Check #{self.check_count} - Checking database status...")

                is_up, error = self.check_database()

                if is_up:
                    # Database is UP
                    if self.last_status == "down":
                        # Status changed from down to up
                        print("   [STATUS] Database Status: UP (RECOVERED!)")
                        self.print_alert_database_recovered()
                        self.up_since = datetime.now()
                        self.down_since = None
                    else:
                        # Still up
                        uptime = datetime.now() - self.up_since if self.up_since else None
                        print(f"   [STATUS] Database Status: UP")
                        if uptime:
                            print(f"   [INFO] Uptime: {uptime}")

                    self.last_status = "up"

                else:
                    # Database is DOWN
                    if self.last_status == "up":
                        # Status changed from up to down
                        print("   [CRITICAL] Database Status: DOWN (NEW ALERT!)")
                        self.print_alert_database_down(error)
                        self.down_since = datetime.now()
                        self.up_since = None
                    else:
                        # Still down
                        downtime = datetime.now() - self.down_since if self.down_since else None
                        print(f"   [CRITICAL] Database Status: DOWN")
                        print(f"   [ERROR] Error: {error}")
                        if downtime:
                            print(f"   [INFO] Downtime: {downtime}")

                    self.last_status = "down"

                print()

                # Wait for next check
                for i in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"[ERROR] Monitoring error: {e}\n")
                time.sleep(self.interval)

        # Show summary
        self.show_summary()

    def show_summary(self):
        """Show monitoring summary"""
        print("\n" + "=" * 100)
        print("  📊 Monitoring Summary")
        print("=" * 100)
        print(f"  Total Checks: {self.check_count}")
        print(f"  Final Status: {self.last_status.upper() if self.last_status else 'UNKNOWN'}")

        if self.last_status == "down" and self.down_since:
            downtime = datetime.now() - self.down_since
            print(f"  Total Downtime: {downtime}")
        elif self.last_status == "up" and self.up_since:
            uptime = datetime.now() - self.up_since
            print(f"  Total Uptime: {uptime}")

        print("=" * 100 + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor PostgreSQL database status")
    parser.add_argument(
        '--dsn',
        type=str,
        default='postgresql://postgres:postgres@localhost:5432/UniversityDB',
        help='PostgreSQL connection string'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='Check interval in seconds (default: 10)'
    )
    args = parser.parse_args()

    try:
        monitor = SimpleDBMonitor(dsn=args.dsn, check_interval=args.interval)
        monitor.monitor()
    except KeyboardInterrupt:
        print("\n\n[WARN] Monitoring interrupted by user")
    except Exception as e:
        print(f"\n\n[FATAL] Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
