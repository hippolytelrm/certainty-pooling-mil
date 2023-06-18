from pathlib import Path

import torch
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from src.config.settings import CONFIG_PATH, DATA_PATH
from src.models.evaluation import evaluation, evaluation_tile
from src.models.model import Paper_network
from src.models.training import train_loop


def single_training(train_loader, validation_loader, validation_loader_tile, config, save_model_path, device):
    config_tensorboard = config.data.training.tensorboard

    if config_tensorboard.use_tensorboard:
        save_dir = Path(config_tensorboard.tensorboard_writer)
        log_dir = save_dir / save_model_path.name.split(".")[0]
        save_dir.mkdir(exist_ok=True)
        log_dir.mkdir(exist_ok=True)
        writer = SummaryWriter(log_dir)

    epochs = config.data.training.epochs
    lr = config.data.training.lr

    model = Paper_network(input_size=2048, dropout=0.5)
    model = model.to(device)

    criterion = torch.nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    if config.data.training.previous_model is not None:
        print("LOADING CHECKPOINTS")
        state_dict = torch.load("/data/data/saved_models/experiment_10/model3461.pt")
        model.load_state_dict(state_dict["model_state_dict"])
        optimizer.load_state_dict(state_dict["optimizer_state_dict"])
        optimizer.param_groups[0]["lr"] = 0.0001

    n = config.data.training.n_monte_carlo

    best_accuracy, best_auc, best_auc_tile = 0, 0, 0

    for epoch in tqdm(range(epochs)):
        running_loss = train_loop(train_loader, model, criterion, optimizer, epoch, device, n=n)

        auc, acc, recall, precision = evaluation(model, validation_loader, device)
        auc_tile, acc_tile, recall_tile, precision_tile = evaluation_tile(
            model=model, loader=validation_loader_tile, n=n, device=device
        )

        if config_tensorboard.use_tensorboard:
            writer.add_scalar("training loss", running_loss, epoch)
            writer.add_scalar("auc", auc, epoch)
            writer.add_scalar("accuracy", acc, epoch)
            writer.add_scalar("recall", recall, epoch)
            writer.add_scalar("precision", precision, epoch)
            writer.add_scalar("auc_tile", auc_tile, epoch)
            writer.add_scalar("accuracy_tile", acc_tile, epoch)
            writer.add_scalar("recall_tile", recall_tile, epoch)
            writer.add_scalar("precision_tile", precision_tile, epoch)

        if auc >= best_auc:
            best_auc = auc

            print("SAVING MODEL AUC")
            print(f"BEST ACCURACY = {acc}, BEST AUC TILE = {auc_tile} , BEST AUC : {best_auc}")

            torch.save(
                obj={
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "auc": auc,
                    "acc": acc,
                    "auc_tile": auc_tile,
                    "acc_tile": acc_tile,
                },
                f=save_model_path,
            )

        if auc_tile >= best_auc_tile:
            best_auc_tile = auc_tile

            print("SAVING MODEL AUC TILE")
            print(f"BEST ACCURACY = {acc}, BEST AUC TILE = {best_auc_tile} , BEST AUC : {auc}")

            torch.save(
                obj={
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "auc": auc,
                    "acc": acc,
                    "auc_tile": auc_tile,
                    "acc_tile": acc_tile,
                },
                f=save_model_path.parent / "model_auc_tile.pt",
            )

    if config_tensorboard.use_tensorboard:
        writer.close()