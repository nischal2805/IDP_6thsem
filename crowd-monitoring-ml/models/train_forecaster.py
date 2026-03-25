"""
Training script for LSTM Density Forecaster.
"""
import numpy as np
import os
import json
import argparse

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ground_server'))
from lstm_forecaster import (
    LSTMForecaster, 
    ForecasterTrainer, 
    DensityTimeSeriesDataset,
    generate_synthetic_data
)


def main():
    parser = argparse.ArgumentParser(description="Train LSTM Density Forecaster")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--duration", type=int, default=7200, help="Training data duration in seconds")
    parser.add_argument("--window", type=int, default=30)
    parser.add_argument("--output", type=str, default="models/forecaster_model.pt")
    parser.add_argument("--device", type=str, default="cuda")
    
    args = parser.parse_args()
    
    if not TORCH_AVAILABLE:
        print("PyTorch required for training")
        return
    
    print("Generating synthetic training data...")
    train_data = generate_synthetic_data(
        duration_seconds=args.duration,
        base_count=50,
        noise_std=5
    )
    
    val_data = generate_synthetic_data(
        duration_seconds=args.duration // 4,
        base_count=50,
        noise_std=5
    )
    
    print(f"Train samples: {len(train_data)}, Val samples: {len(val_data)}")
    
    # Create model
    model = LSTMForecaster(
        input_size=1,
        hidden_size=64,
        num_layers=2,
        dropout=0.2,
        num_horizons=3,
        bidirectional=True
    )
    
    print(f"Model parameters: {sum(p.numel() for p in model.parameters())}")
    
    # Train
    device = args.device if torch.cuda.is_available() else "cpu"
    print(f"Training on {device}")
    
    trainer = ForecasterTrainer(model, device=device, learning_rate=args.lr)
    
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    
    history = trainer.train(
        train_data=train_data,
        val_data=val_data,
        epochs=args.epochs,
        batch_size=args.batch_size,
        window_size=args.window,
        save_path=args.output
    )
    
    # Save history
    with open(args.output.replace('.pt', '_history.json'), 'w') as f:
        json.dump(history, f)
    
    print(f"Model saved to {args.output}")


if __name__ == "__main__":
    main()
