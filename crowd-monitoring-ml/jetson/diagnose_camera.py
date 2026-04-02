#!/usr/bin/env python3
"""
Camera Diagnostic Script for Jetson Orin Nano
Comprehensive debugging tool for camera connectivity and configuration issues
"""

import os
import sys
import cv2
import subprocess
import glob
import time
from pathlib import Path

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

def check_video_devices():
    """Check for available video devices"""
    print_header("1. Checking for Video Devices")
    
    video_devices = glob.glob('/dev/video*')
    
    if not video_devices:
        print_error("No video devices found in /dev/")
        print_info("Solutions:")
        print("   - Check if camera is physically connected")
        print("   - Run: lsusb (to see USB devices)")
        print("   - Run: dmesg | grep video (to check kernel messages)")
        print("   - Try: sudo modprobe v4l2loopback (if using virtual cameras)")
        return []
    
    print_success(f"Found {len(video_devices)} video device(s):")
    for device in sorted(video_devices):
        print(f"   {device}")
    
    return sorted(video_devices)

def check_device_permissions(devices):
    """Check permissions on video devices"""
    print_header("2. Checking Device Permissions")
    
    accessible_devices = []
    current_user = os.getenv('USER', 'unknown')
    
    for device in devices:
        try:
            # Check if readable
            if os.access(device, os.R_OK):
                print_success(f"{device} is readable")
                accessible_devices.append(device)
            else:
                print_error(f"{device} is NOT readable")
                
                # Get file permissions
                stat_info = os.stat(device)
                mode = oct(stat_info.st_mode)[-3:]
                
                print_info(f"Current permissions: {mode}")
                print_info("Solutions:")
                print(f"   - Add user to video group: sudo usermod -aG video {current_user}")
                print(f"   - Or change permissions: sudo chmod 666 {device}")
                print(f"   - Then log out and back in")
                
        except Exception as e:
            print_error(f"Error checking {device}: {e}")
    
    return accessible_devices

def get_opencv_build_info():
    """Get OpenCV build information"""
    print_header("3. OpenCV Build Information")
    
    print_info(f"OpenCV Version: {cv2.__version__}")
    
    build_info = cv2.getBuildInformation()
    
    # Check for important features
    features = {
        'Video I/O': ['V4L/V4L2', 'GStreamer'],
        'FFMPEG': ['avcodec', 'avformat'],
    }
    
    for category, keywords in features.items():
        print(f"\n{Colors.BOLD}{category}:{Colors.RESET}")
        for keyword in keywords:
            if keyword in build_info:
                # Find the line with this keyword
                for line in build_info.split('\n'):
                    if keyword in line:
                        if 'YES' in line or 'yes' in line:
                            print_success(f"{keyword} support: ENABLED")
                        elif 'NO' in line or 'no' in line:
                            print_warning(f"{keyword} support: DISABLED")
                        else:
                            print_info(line.strip())
                        break
    
    # Check backend availability
    print(f"\n{Colors.BOLD}Available Backends:{Colors.RESET}")
    backends = [
        ('CAP_V4L2', cv2.CAP_V4L2, 'Video4Linux2'),
        ('CAP_GSTREAMER', cv2.CAP_GSTREAMER, 'GStreamer'),
        ('CAP_FFMPEG', cv2.CAP_FFMPEG, 'FFMPEG'),
    ]
    
    for name, backend, desc in backends:
        try:
            # Try to get backend name
            backend_name = cv2.videoio_registry.getBackendName(backend)
            print_success(f"{desc} ({name}): Available")
        except Exception as e:
            print_warning(f"{desc} ({name}): Not available")

def check_device_in_use(device):
    """Check if a device is already in use"""
    try:
        result = subprocess.run(
            ['lsof', device],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print_warning(f"Device {device} is in use by:")
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                print(f"      {line}")
            return True
        return False
    except subprocess.TimeoutExpired:
        print_warning(f"Timeout checking if {device} is in use")
        return False
    except FileNotFoundError:
        print_info("'lsof' command not available, skipping in-use check")
        return False
    except Exception as e:
        print_warning(f"Could not check if {device} is in use: {e}")
        return False

def test_camera_with_backend(device, backend_name, backend_id):
    """Test camera with specific backend"""
    print(f"\n{Colors.BOLD}Testing {device} with {backend_name}:{Colors.RESET}")
    
    try:
        cap = cv2.VideoCapture(device, backend_id)
        
        if not cap.isOpened():
            print_error(f"Failed to open with {backend_name}")
            return None
        
        print_success(f"Opened successfully with {backend_name}")
        
        # Get camera properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        
        print_info(f"Resolution: {width}x{height}")
        print_info(f"FPS: {fps}")
        print_info(f"FourCC: {fourcc_str}")
        
        # Try to read a frame
        print_info("Attempting to capture frame...")
        ret, frame = cap.read()
        
        if ret:
            print_success("Successfully captured frame!")
            print_info(f"Frame shape: {frame.shape}")
            print_info(f"Frame dtype: {frame.dtype}")
            
            # Try to capture multiple frames to test stability
            success_count = 0
            fail_count = 0
            frame_times = []
            
            for i in range(10):
                start_time = time.time()
                ret, frame = cap.read()
                frame_time = time.time() - start_time
                
                if ret:
                    success_count += 1
                    frame_times.append(frame_time)
                else:
                    fail_count += 1
            
            if success_count == 10:
                avg_time = sum(frame_times) / len(frame_times)
                actual_fps = 1.0 / avg_time if avg_time > 0 else 0
                print_success(f"Captured 10/10 frames successfully")
                print_info(f"Actual FPS: {actual_fps:.2f}")
            else:
                print_warning(f"Captured {success_count}/10 frames (failed: {fail_count})")
        else:
            print_error("Failed to capture frame")
            print_info("Solutions:")
            print("   - Check camera connection")
            print("   - Try different resolution/codec")
            print("   - Check dmesg for errors: dmesg | tail -50")
        
        cap.release()
        return True
        
    except Exception as e:
        print_error(f"Exception with {backend_name}: {e}")
        return None

def test_different_codecs(device):
    """Test different codecs on the device"""
    print(f"\n{Colors.BOLD}Testing Different Codecs on {device}:{Colors.RESET}")
    
    codecs = [
        ('MJPEG', cv2.VideoWriter_fourcc(*'MJPG')),
        ('YUYV', cv2.VideoWriter_fourcc(*'YUYV')),
        ('H264', cv2.VideoWriter_fourcc(*'H264')),
        ('VP80', cv2.VideoWriter_fourcc(*'VP80')),
    ]
    
    successful_codecs = []
    
    for codec_name, fourcc in codecs:
        try:
            cap = cv2.VideoCapture(device)
            if not cap.isOpened():
                continue
            
            # Try setting the codec
            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            
            # Try to read a frame
            ret, frame = cap.read()
            
            if ret:
                actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                actual_fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
                print_success(f"{codec_name}: Working (actual: {actual_fourcc_str})")
                successful_codecs.append(codec_name)
            else:
                print_warning(f"{codec_name}: Could not capture frame")
            
            cap.release()
            
        except Exception as e:
            print_error(f"{codec_name}: Error - {e}")
    
    return successful_codecs

def test_resolutions(device):
    """Test different resolutions"""
    print(f"\n{Colors.BOLD}Testing Different Resolutions on {device}:{Colors.RESET}")
    
    resolutions = [
        (640, 480, 'VGA'),
        (1280, 720, 'HD 720p'),
        (1920, 1080, 'Full HD 1080p'),
        (3840, 2160, '4K UHD'),
    ]
    
    successful_resolutions = []
    
    for width, height, name in resolutions:
        try:
            cap = cv2.VideoCapture(device)
            if not cap.isOpened():
                break
            
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            ret, frame = cap.read()
            
            if ret and actual_width == width and actual_height == height:
                print_success(f"{name} ({width}x{height}): Supported")
                successful_resolutions.append((width, height, name))
            elif ret:
                print_warning(f"{name} ({width}x{height}): Camera returned {actual_width}x{actual_height}")
            else:
                print_warning(f"{name} ({width}x{height}): Not supported")
            
            cap.release()
            
        except Exception as e:
            print_error(f"{name}: Error - {e}")
    
    return successful_resolutions

def get_v4l2_info(device):
    """Get detailed V4L2 information using v4l2-ctl"""
    print(f"\n{Colors.BOLD}V4L2 Device Information for {device}:{Colors.RESET}")
    
    try:
        # Check if v4l2-ctl is available
        result = subprocess.run(
            ['v4l2-ctl', '--device', device, '--all'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print_success("v4l2-ctl information:")
            print(result.stdout)
        else:
            print_error(f"v4l2-ctl failed: {result.stderr}")
            
    except FileNotFoundError:
        print_warning("v4l2-ctl not installed")
        print_info("Install with: sudo apt-get install v4l-utils")
    except subprocess.TimeoutExpired:
        print_error("v4l2-ctl command timed out")
    except Exception as e:
        print_warning(f"Could not get V4L2 info: {e}")

def generate_summary_report(results):
    """Generate a summary report"""
    print_header("Summary Report")
    
    print(f"{Colors.BOLD}Video Devices Found:{Colors.RESET} {results['devices_found']}")
    print(f"{Colors.BOLD}Accessible Devices:{Colors.RESET} {results['accessible_devices']}")
    print(f"{Colors.BOLD}Working Devices:{Colors.RESET} {results['working_devices']}")
    
    if results['working_devices'] > 0:
        print_success("\nAt least one camera is working!")
        print_info("\nRecommendations:")
        print("   - Use the working device(s) identified above")
        print("   - Consider the codec and resolution that worked best")
        print("   - Check the sample code in the diagnostic output")
    else:
        print_error("\nNo working cameras found!")
        print_info("\nTroubleshooting Steps:")
        print("   1. Check physical camera connection")
        print("   2. Run: lsusb (to verify USB devices)")
        print("   3. Run: dmesg | grep -i video (to check kernel messages)")
        print("   4. Verify user permissions: groups | grep video")
        print("   5. Try: sudo apt-get install v4l-utils")
        print("   6. Check if camera works in other apps: cheese or guvcview")
    
    if results.get('sample_code'):
        print(f"\n{Colors.BOLD}Sample Code for Working Configuration:{Colors.RESET}")
        print(f"{Colors.GREEN}{results['sample_code']}{Colors.RESET}")

def main():
    """Main diagnostic function"""
    print_header("Jetson Orin Nano - Camera Diagnostic Tool")
    print(f"{Colors.BOLD}Starting comprehensive camera diagnostics...{Colors.RESET}\n")
    
    results = {
        'devices_found': 0,
        'accessible_devices': 0,
        'working_devices': 0,
        'sample_code': None
    }
    
    # Step 1: Find video devices
    video_devices = check_video_devices()
    results['devices_found'] = len(video_devices)
    
    if not video_devices:
        generate_summary_report(results)
        return 1
    
    # Step 2: Check permissions
    accessible_devices = check_device_permissions(video_devices)
    results['accessible_devices'] = len(accessible_devices)
    
    if not accessible_devices:
        print_error("\nNo accessible devices found. Fix permissions and run again.")
        generate_summary_report(results)
        return 1
    
    # Step 3: OpenCV build info
    get_opencv_build_info()
    
    # Step 4: Test each accessible device
    print_header("4. Testing Camera Devices")
    
    for device in accessible_devices:
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'─' * 70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}Testing Device: {device}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'─' * 70}{Colors.RESET}")
        
        # Check if device is in use
        in_use = check_device_in_use(device)
        
        # Try different backends
        backends = [
            ('V4L2', cv2.CAP_V4L2),
            ('Default', cv2.CAP_ANY),
        ]
        
        device_working = False
        for backend_name, backend_id in backends:
            result = test_camera_with_backend(device, backend_name, backend_id)
            if result:
                device_working = True
                if not results['sample_code']:
                    # Generate sample code for first working device
                    results['sample_code'] = f"""
import cv2

# Open camera with working configuration
cap = cv2.VideoCapture('{device}', cv2.CAP_V4L2)

if cap.isOpened():
    ret, frame = cap.read()
    if ret:
        print(f"Frame captured: {{frame.shape}}")
        cv2.imshow('Camera', frame)
        cv2.waitKey(0)
    cap.release()
else:
    print("Failed to open camera")
cv2.destroyAllWindows()
"""
                break
        
        if device_working:
            results['working_devices'] += 1
            
            # Test codecs
            test_different_codecs(device)
            
            # Test resolutions
            test_resolutions(device)
            
            # Get V4L2 info
            get_v4l2_info(device)
        else:
            print_error(f"\n{device} is not working with any backend")
    
    # Generate summary
    generate_summary_report(results)
    
    return 0 if results['working_devices'] > 0 else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Diagnostic interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
