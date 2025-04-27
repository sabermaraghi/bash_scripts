#!/usr/bin/env python3

import subprocess
import time
from datetime import datetime
import re
import os
import sys
import stat

# Configuration
LATENCY_THRESHOLD = 100  # Latency threshold in milliseconds
LOG_FILE = "/var/log/dns-update.log"
MAX_INTERVAL_MINUTES = 40  # Maximum interval between runs to detect scheduling issues
SCRIPT_PATH = "/usr/local/bin/setup_and_update_dns.py"

# List of DNS servers to test (updated as per request)
DNS_SERVERS = [
    "1.1.1.1",        # Cloudflare
    "1.0.0.1",        # Cloudflare
    "172.20.20.16",   # Hamrah-Mechanic
    "85.15.1.14",     # Shatel
    "85.15.1.15",     # Shatel
    "10.202.10.202",  # 403
    "10.202.10.102",  # 403
    "209.244.0.3",    # Level3
    "209.244.0.4",    # Level3
    "10.202.10.10",   # radar.game
    "10.202.10.11",   # radar.game
    "78.157.42.100",  # electrotm.org
    "78.157.42.101",  # electrotm.org
    "94.103.125.157", # sheltertm.com
    "94.103.125.158", # sheltertm.com
    "181.41.194.177", # beshkanapp.ir
    "181.41.194.186", # beshkanapp.ir
    "5.202.100.100",  # pishgaman.net
    "5.202.100.101",  # pishgaman.net
    "172.29.0.100",   # Host-Iran
    "172.29.2.100",   # Host-Iran
    "185.55.226.26",  # Begzar
    "185.55.225.25",  # Begzar
    "178.22.122.100", # Shecan
    "185.51.200.2"    # Shecan
]

# Fallback DNS server if none are reachable
FALLBACK_DNS = "1.1.1.1"  # Cloudflare

# Function to log messages
def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"{timestamp}: {message}"
    print(log_message)
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")

# Function to check if the script is running as root
def check_root():
    if os.geteuid() != 0:
        write_log("This script must be run as root. Use sudo.")
        sys.exit(1)

# Function to set up the log directory and file
def setup_logging():
    log_dir = os.path.dirname(LOG_FILE)
    write_log(f"Creating log directory {log_dir} if it doesn't exist...")
    os.makedirs(log_dir, exist_ok=True)
    
    write_log(f"Creating log file {LOG_FILE} if it doesn't exist...")
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "a") as f:
            pass
    os.chmod(LOG_FILE, 0o666)  # Set permissions to rw-rw-rw-
    write_log(f"Log file permissions set to 666 for {LOG_FILE}.")

# Function to set up the cron job
def setup_cron():
    cron_job = f"*/30 * * * * /usr/bin/python3 {SCRIPT_PATH} --run\n"
    cron_file = "/tmp/crontab.tmp"
    
    write_log("Configuring cron job to run the script every 30 minutes...")
    try:
        # Get current crontab and remove any existing entries for this script
        current_crontab = subprocess.run(
            ["crontab", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        ).stdout
        with open(cron_file, "w") as f:
            for line in current_crontab.splitlines():
                if SCRIPT_PATH not in line:
                    f.write(line + "\n")
            f.write(cron_job)
        subprocess.run(["crontab", cron_file], check=True)
        os.remove(cron_file)
        write_log(f"Cron job configured: {cron_job.strip()}")
    except Exception as e:
        write_log(f"Error setting up cron job: {str(e)}")

# Function to check the last run time from the log file
def check_last_run():
    last_run_time = None
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            for line in reversed(lines):
                match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if match:
                    last_run_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                    break
    if last_run_time:
        time_since_last_run = (datetime.now() - last_run_time).total_seconds() / 60
        if time_since_last_run > MAX_INTERVAL_MINUTES:
            write_log(f"Warning: Last run was more than {MAX_INTERVAL_MINUTES} minutes ago ({last_run_time}). Scheduler may have failed.")

# Function to get active network interfaces
def get_active_interfaces():
    try:
        result = subprocess.run(
            ["ip", "link"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        interfaces = []
        for line in result.stdout.splitlines():
            # Match lines like "2: enp88s0: <BROADCAST,MULTICAST,UP,LOWER_UP> ..."
            match = re.match(r"\d+: (\w+): <[^>]+>.*state (UP|DOWN)", line)
            if match:
                interface = match.group(1)
                state = match.group(2)
                # Exclude loopback and include only relevant interfaces
                if interface != "lo":
                    interfaces.append({"name": interface, "state": state})
        return interfaces
    except Exception as e:
        write_log(f"Error getting network interfaces: {str(e)}")
        return []

# Function to test DNS server latency
def test_dns_server(dns_server):
    try:
        result = subprocess.run(
            ["ping", "-c", "2", dns_server],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            raise Exception(f"Ping failed: {result.stderr}")

        match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms", result.stdout)
        if match:
            avg_latency = float(match.group(1))
            write_log(f"DNS server {dns_server} is reachable with average latency: {avg_latency} ms")
            return {"dns": dns_server, "latency": avg_latency, "reachable": True}
        else:
            raise Exception("Could not parse ping output.")
    except (subprocess.TimeoutExpired, Exception) as e:
        write_log(f"DNS server {dns_server} is not reachable. Error: {str(e)}")
        return {"dns": dns_server, "latency": float("inf"), "reachable": False}

# Function to get current DNS servers for an interface
def get_current_dns(interface):
    try:
        result = subprocess.run(
            ["resolvectl", "status", interface],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        dns_servers = []
        for line in result.stdout.splitlines():
            if "DNS Servers" in line:
                servers = line.split(":")[1].strip().split()
                dns_servers.extend(servers)
        if dns_servers:
            write_log(f"Current DNS servers for {interface}: {', '.join(dns_servers)}")
            return dns_servers[0]  # Return the first DNS server
        else:
            write_log(f"No DNS servers found in resolvectl output for {interface}.")
            return None
    except Exception as e:
        write_log(f"Error getting current DNS servers for {interface}: {str(e)}")
        return None

# Function to set DNS server for an interface
def set_dns_server(interface, dns_server):
    try:
        if "docker" in interface.lower():
            write_log(f"Interface {interface} appears to be a Docker bridge. Attempting to set DNS, but this may not be supported.")
        subprocess.run(
            ["resolvectl", "set-dns", interface, dns_server],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        subprocess.run(
            ["resolvectl", "flush-caches"],
            check=True
        )
        subprocess.run(
            ["systemctl", "restart", "systemd-resolved"],
            check=True
        )
        write_log(f"DNS server updated to {dns_server} for interface {interface}.")
        
        current_dns = get_current_dns(interface)
        if current_dns == dns_server:
            write_log(f"Updated DNS settings verified for {interface}: {current_dns}")
        else:
            write_log(f"Failed to verify updated DNS settings for {interface}. Current DNS: {current_dns}")
        return True
    except Exception as e:
        write_log(f"Error setting DNS server {dns_server} for {interface}: {str(e)}")
        return False

# Main script
def main():
    # Check if the script is being run in setup mode or run mode
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        check_root()
        write_log("Setup mode: Configuring script, logging, and cron job...")

        # Step 1: Copy this script to /usr/local/bin/
        if not os.path.exists(SCRIPT_PATH):
            write_log(f"Copying script to {SCRIPT_PATH}...")
            with open(sys.argv[0], "r") as src, open(SCRIPT_PATH, "w") as dst:
                dst.write(src.read())
            os.chmod(SCRIPT_PATH, 0o755)  # Set permissions to rwxr-xr-x
            write_log(f"Script copied and permissions set to 755 for {SCRIPT_PATH}.")

        # Step 2: Set up logging
        setup_logging()

        # Step 3: Set up cron job
        setup_cron()

        # Step 4: Test the script in run mode
        write_log("Testing the script in run mode...")
        subprocess.run([sys.executable, SCRIPT_PATH, "--run"])

        write_log("Setup complete. The script will now run every 30 minutes via cron.")
        write_log(f"Check the log file at {LOG_FILE} for details.")

    else:
        # Run mode: Perform the DNS check and update
        write_log("Run mode: Checking and updating DNS settings...")
        check_last_run()

        # Test basic network connectivity
        internet_test = test_dns_server("8.8.8.8")
        if not internet_test["reachable"]:
            write_log("Network connectivity test: Failed to ping 8.8.8.8. There may be a network issue.")
            interfaces = get_active_interfaces()
            for iface in interfaces:
                if iface["state"] == "UP":
                    write_log(f"Setting fallback DNS server {FALLBACK_DNS} for {iface['name']} due to network issues...")
                    set_dns_server(iface["name"], FALLBACK_DNS)
            return  # Exit early if there's no network connectivity

        # Get active interfaces
        interfaces = get_active_interfaces()
        if not interfaces:
            write_log("No network interfaces found. Exiting.")
            return

        for iface in interfaces:
            interface_name = iface["name"]
            interface_state = iface["state"]
            write_log(f"Processing interface {interface_name} (State: {interface_state})...")

            if interface_state != "UP":
                write_log(f"Interface {interface_name} is not UP. Skipping DNS check.")
                continue

            # Get current DNS server
            current_dns = get_current_dns(interface_name)
            if not current_dns:
                write_log(f"No current DNS server found for {interface_name}. Setting fallback DNS server.")
                if set_dns_server(interface_name, FALLBACK_DNS):
                    current_dns = get_current_dns(interface_name)
                    if current_dns != FALLBACK_DNS:
                        write_log(f"Failed to set fallback DNS {FALLBACK_DNS} for {interface_name}. Current DNS: {current_dns}")
                        continue
                    else:
                        current_dns = FALLBACK_DNS
                else:
                    write_log(f"Failed to set fallback DNS {FALLBACK_DNS} for {interface_name}. Skipping.")
                    continue

            # Test the current DNS server
            current_dns_result = test_dns_server(current_dns)
            update_needed = False
            if not current_dns_result["reachable"] or current_dns_result["latency"] > LATENCY_THRESHOLD:
                write_log(f"Current DNS {current_dns} for {interface_name} is either unreachable or too slow (Latency: {current_dns_result['latency']} ms, Threshold: {LATENCY_THRESHOLD} ms)")
                update_needed = True
            else:
                write_log(f"Current DNS {current_dns} for {interface_name} is performing well (Latency: {current_dns_result['latency']} ms).")

            # If update is needed, test all DNS servers and find the fastest
            if update_needed:
                write_log(f"Testing all DNS servers to find the fastest one for {interface_name}...")
                dns_results = []
                for dns in DNS_SERVERS:
                    result = test_dns_server(dns)
                    dns_results.append(result)

                fastest_dns = [r for r in dns_results if r["reachable"]]
                fastest_dns.sort(key=lambda x: x["latency"])

                if fastest_dns:
                    new_dns = fastest_dns[0]["dns"]
                    write_log(f"Fastest DNS server for {interface_name}: {new_dns} (Latency: {fastest_dns[0]['latency']} ms)")
                    if set_dns_server(interface_name, new_dns):
                        current_dns = get_current_dns(interface_name)
                        if current_dns != new_dns:
                            write_log(f"Failed to set new DNS {new_dns} for {interface_name}. Current DNS: {current_dns}")
                    else:
                        write_log(f"Failed to set new DNS {new_dns} for {interface_name}. Keeping current settings.")
                else:
                    write_log(f"No reachable DNS servers found for {interface_name}.")
                    write_log(f"Falling back to default DNS server: {FALLBACK_DNS} for {interface_name}")
                    set_dns_server(interface_name, FALLBACK_DNS)
            else:
                write_log(f"No changes needed for {interface_name}.")

        write_log("Script completed.")

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--run":
            main()
        elif len(sys.argv) > 1 and sys.argv[1] == "--setup":
            main()
        else:
            write_log("Usage: Run with --setup to configure the script, or --run to check and update DNS.")
            write_log("Example: sudo python3 setup_and_update_dns.py --setup")
    except Exception as e:
        write_log(f"Error in script execution: {str(e)}")
        sys.exit(1)
