"""
Training script for LSTM Fall Classifier.
Uses Le2i FDD dataset format for training.
"""
import numpy as np
import os
import json
from typing import List, Tuple
import argparse

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorch not available")

# Import the LSTM classifier
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'jetson'))
from fall_detector import LSTMFallClassifier


class FallDataset(Dataset):
    """Dataset for fall detection training."""
    
    def __init__(self, sequences: List[np.ndarray], labels: List[int]):
        """
        Args:
            sequences: List of keypoint sequences (seq_len, 17, 2)
            labels: List of labels (0=no fall, 1=fall)
        """
        self.sequences = sequences
        self.labels = labels
    
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx):
        seq = self.sequences[idx]
        # Flatten keypoints: (seq_len, 17, 2) -> (seq_len, 34)
        seq_flat = seq.reshape(seq.shape[0], -1)
        return torch.FloatTensor(seq_flat), torch.LongTensor([self.labels[idx]])


def generate_synthetic_fall_data(
    num_samples: int = 1000,
    seq_len: int = 20,
    fall_ratio: float = 0.3
) -> Tuple[List[np.ndarray], List[int]]:
    """
    Generate synthetic fall/non-fall sequences for training.
    
    In production, replace this with real Le2i/URFD dataset loading.
    """
    sequences = []
    labels = []
    
    num_falls = int(num_samples * fall_ratio)
    
    # Generate fall sequences
    for _ in range(num_falls):
        seq = np.zeros((seq_len, 17, 2))
        
        # Simulate falling motion: hip keypoints (11, 12) move down rapidly
        fall_frame = np.random.randint(5, 15)
        
        for t in range(seq_len):
            # Base standing pose
            for k in range(17):
                seq[t, k, 0] = 0.5 + np.random.normal(0, 0.05)  # x
                seq[t, k, 1] = 0.3 + k * 0.03 + np.random.normal(0, 0.02)  # y
            
            # Fall motion after fall_frame
            if t >= fall_frame:
                fall_progress = min((t - fall_frame) / 5, 1.0)
                # Hip keypoints drop
                seq[t, 11, 1] += fall_progress * 0.4
                seq[t, 12, 1] += fall_progress * 0.4
                # Shoulders widen (aspect ratio change)
                seq[t, 5, 0] -= fall_progress * 0.1
                seq[t, 6, 0] += fall_progress * 0.1
        
        sequences.append(seq)
        labels.append(1)
    
    # Generate non-fall sequences
    for _ in range(num_samples - num_falls):
        seq = np.zeros((seq_len, 17, 2))
        
        # Random walking/standing poses
        base_motion = np.random.choice(['standing', 'walking', 'sitting'])
        
        for t in range(seq_len):
            for k in range(17):
                seq[t, k, 0] = 0.5 + np.random.normal(0, 0.08)
                seq[t, k, 1] = 0.3 + k * 0.03 + np.random.normal(0, 0.03)
            
            if base_motion == 'walking':
                # Slight horizontal oscillation
                seq[t, :, 0] += 0.05 * np.sin(t * 0.5)
            elif base_motion == 'sitting':
                # Lower hip position (but not falling pattern)
                seq[t, 11:13, 1] += 0.15
        
        sequences.append(seq)
        labels.append(0)
    
    # Shuffle
    combined = list(zip(sequences, labels))
    np.random.shuffle(combined)
    sequences, labels = zip(*combined)
    
    return list(sequences), list(labels)


def train_fall_classifier(
    model: LSTMFallClassifier,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 50,
    lr: float = 0.001,
    device: str = "cuda",
    save_path: str = "fall_classifier.pt"
):
    """Train the fall classifier."""
    model = model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = nn.CrossEntropyLoss()
    
    best_val_acc = 0
    history = {'train_loss': [], 'train_acc': [], 'val_loss': [], 'val_acc': []}
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        train_correct = 0
        train_total = 0
        
        for x, y in train_loader:
            x, y = x.to(device), y.squeeze().to(device)
            
            optimizer.zero_grad()
            output = model(x)
            loss = criterion(output, y)
            loss.backward()
            
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = torch.max(output, 1)
            train_total += y.size(0)
            train_correct += (predicted == y).sum().item()
        
        train_acc = train_correct / train_total
        
        # Validation
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.squeeze().to(device)
                output = model(x)
                loss = criterion(output, y)
                
                val_loss += loss.item()
                _, predicted = torch.max(output, 1)
                val_total += y.size(0)
                val_correct += (predicted == y).sum().item()
        
        val_acc = val_correct / val_total
        scheduler.step(val_loss)
        
        history['train_loss'].append(train_loss / len(train_loader))
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss / len(val_loader))
        history['val_acc'].append(val_acc)
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), save_path)
        
        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch+1}/{epochs}")
            print(f"  Train Loss: {train_loss/len(train_loader):.4f}, Acc: {train_acc:.4f}")
            print(f"  Val Loss: {val_loss/len(val_loader):.4f}, Acc: {val_acc:.4f}")
    
    print(f"\nTraining complete. Best validation accuracy: {best_val_acc:.4f}")
    return history


def main():
    parser = argparse.ArgumentParser(description="Train LSTM Fall Classifier")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--output", type=str, default="models/fall_classifier.pt")
    parser.add_argument("--device", type=str, default="cuda")
    
    args = parser.parse_args()
    
    if not TORCH_AVAILABLE:
        print("PyTorch required for training")
        return
    
    print("Generating synthetic training data...")
    sequences, labels = generate_synthetic_fall_data(args.samples)
    
    # Split train/val
    split_idx = int(len(sequences) * 0.8)
    train_seqs, train_labels = sequences[:split_idx], labels[:split_idx]
    val_seqs, val_labels = sequences[split_idx:], labels[split_idx:]
    
    train_dataset = FallDataset(train_seqs, train_labels)
    val_dataset = FallDataset(val_seqs, val_labels)
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    
    print(f"Train samples: {len(train_dataset)}, Val samples: {len(val_dataset)}")
    
    # Create model
    model = LSTMFallClassifier(
        input_size=34,
        hidden_size=64,
        num_layers=2,
        dropout=0.3,
        num_classes=2
    )
    
    print(f"Model parameters: {sum(p.numel() for p in model.parameters())}")
    
    # Train
    device = args.device if torch.cuda.is_available() else "cpu"
    print(f"Training on {device}")
    
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    
    history = train_fall_classifier(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        epochs=args.epochs,
        lr=args.lr,
        device=device,
        save_path=args.output
    )
    
    # Save history
    with open(args.output.replace('.pt', '_history.json'), 'w') as f:
        json.dump(history, f)
    
    print(f"Model saved to {args.output}")


if __name__ == "__main__":
    main()
