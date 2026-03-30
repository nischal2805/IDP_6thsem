"""
Quick Test Script for Server OpenCV Pipeline
Tests all components with your webcam
"""

import sys
import cv2

def test_imports():
    """Test if all required libraries are installed"""
    print("="*60)
    print("TESTING IMPORTS")
    print("="*60)
    
    try:
        import cv2
        print(f"✓ OpenCV version: {cv2.__version__}")
    except ImportError:
        print("✗ OpenCV not installed. Run: pip install opencv-python")
        return False
    
    try:
        import numpy as np
        print(f"✓ NumPy version: {np.__version__}")
    except ImportError:
        print("✗ NumPy not installed. Run: pip install numpy")
        return False
    
    print("\n✓ All required libraries installed!\n")
    return True


def test_camera():
    """Test if camera is accessible"""
    print("="*60)
    print("TESTING CAMERA")
    print("="*60)
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("✗ Could not open camera at index 0")
        print("  Try checking:")
        print("  - Is camera connected?")
        print("  - Is camera being used by another app?")
        print("  - Try index 1 or 2")
        return False
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("✗ Camera opened but could not read frame")
        return False
    
    print(f"✓ Camera working! Resolution: {frame.shape[1]}x{frame.shape[0]}")
    print()
    return True


def test_modules():
    """Test if custom modules can be imported"""
    print("="*60)
    print("TESTING CUSTOM MODULES")
    print("="*60)
    
    modules = [
        ("camera_receiver", "CameraReceiver"),
        ("opencv_crowd_detector", "OpenCVCrowdDetector"),
        ("density_heatmap", "DensityHeatmapGenerator"),
        ("optical_flow_analyzer", "OpticalFlowAnalyzer"),
    ]
    
    all_ok = True
    
    for module_name, class_name in modules:
        try:
            module = __import__(module_name)
            getattr(module, class_name)
            print(f"✓ {module_name}.{class_name}")
        except ImportError:
            print(f"✗ Could not import {module_name}")
            print(f"  Make sure you're in the server_opencv directory")
            all_ok = False
        except AttributeError:
            print(f"✗ {module_name} missing {class_name}")
            all_ok = False
    
    if all_ok:
        print("\n✓ All modules can be imported!\n")
    
    return all_ok


def run_quick_test():
    """Run a 5-second test of the pipeline"""
    print("="*60)
    print("QUICK PIPELINE TEST (5 seconds)")
    print("="*60)
    print("\nInitializing components...")
    
    try:
        from camera_receiver import CameraReceiver, CameraConfig
        from opencv_crowd_detector import OpenCVCrowdDetector, DetectionMethod
        
        # Initialize camera
        cam_config = CameraConfig(source=0, width=640, height=480, fps=30)
        camera = CameraReceiver(cam_config)
        
        # Initialize detector
        detector = OpenCVCrowdDetector(method=DetectionMethod.MOG2)
        
        print("✓ Components initialized")
        print("\nProcessing 150 frames (5 seconds)...")
        print("This will warm up the background model...\n")
        
        import time
        frame_count = 0
        start_time = time.time()
        
        while frame_count < 150:
            ret, frame = camera.read_frame()
            
            if not ret or frame is None:
                print(f"✗ Failed to read frame {frame_count}")
                continue
            
            # Detect crowd
            result = detector.detect(frame)
            frame_count += 1
            
            # Show progress every 30 frames
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"  Frame {frame_count}/150 | FPS: {fps:.1f} | Count: {result.person_count}")
        
        elapsed = time.time() - start_time
        avg_fps = frame_count / elapsed
        
        camera.release()
        
        print(f"\n✓ Test completed!")
        print(f"  Processed {frame_count} frames in {elapsed:.2f}s")
        print(f"  Average FPS: {avg_fps:.1f}")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner"""
    print("\n" + "="*60)
    print("SERVER OPENCV PIPELINE - SYSTEM TEST")
    print("="*60 + "\n")
    
    # Test 1: Imports
    if not test_imports():
        print("\n❌ Import test failed. Install missing packages.")
        return 1
    
    # Test 2: Camera
    if not test_camera():
        print("\n❌ Camera test failed. Check camera connection.")
        print("\nYou can still test with a video file by editing camera_source in server_pipeline.py")
        return 1
    
    # Test 3: Modules
    if not test_modules():
        print("\n❌ Module test failed. Make sure you're in server_opencv directory.")
        return 1
    
    # Test 4: Quick pipeline test
    if not run_quick_test():
        print("\n❌ Pipeline test failed.")
        return 1
    
    # All tests passed
    print("="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print("\nYou're ready to run the full pipeline:")
    print("  python server_pipeline.py")
    print("\nOr test individual modules:")
    print("  python camera_receiver.py")
    print("  python opencv_crowd_detector.py")
    print("  python density_heatmap.py")
    print("  python optical_flow_analyzer.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
