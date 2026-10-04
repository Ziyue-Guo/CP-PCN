# Environment and legacy-script guide

## Environment scope

The new data checker runs on **Python 3.11+ with the standard library**. Its tests do not install or import the model stack.

The original README mentioned Python 3.7.4 / PyTorch 1.0.1, as does the upstream [PF-Net README](https://github.com/zztianzz/PF-Net-Point-Fractal-Network), but also prescribed Python 3.8+. That text is historical context, not a validated CP-PCN dependency lock. No complete environment export is available here.

| Workflow | Dependencies / external resources |
| --- | --- |
| Model, training, inference | `torch`, `torchvision`, `numpy`, compatible CUDA stack |
| Data generation | Above plus `open3d`, `trimesh` and a working ray-query backend |
| COLMAP batch helper | Windows command shell, conda environment, external COLMAP and Instant-NGP `colmap2nerf.py` |
| Data checker | Python standard library only |

PyEmbree was mentioned by the old README but is not directly imported; ray-backend installation must be tested for the intended Trimesh/platform combination. Consult [official PyTorch installation history](https://pytorch.org/get-started/previous-versions/) when recovering an environment, and verify it with a known checkpoint. This update does not provide an invented version lock or claim a tested modern model environment.

**CUDA is required by the preserved model code:** `get_graph_feature` allocates on `torch.device('cuda')`, and prediction/export scripts call `.cuda()`. Their apparent CPU fallback and `--cuda` option do not make CPU inference work.

Most legacy entry points execute work at module scope. Do not import them to perform a lightweight health check; even command-line help imports their dependencies first.

## Training: Train_RP_PCN.py

The correct filename is `Train_RP_PCN.py`. Before executing it:

1. Replace both `PartDataset(root='../dataset/mydata', ...)` calls with the intended dataset root. From the repository directory the existing path points outside the bundled dataset. **`--dataroot` is currently ignored.**
2. Prepare independent data splits and compatible point counts; audit them with `tools/check_dataset.py`.
3. Replace the absolute `D:/PhD_Study/.../Checkpoint/loss_PFNet.txt` log path and `../Trained_Model` save paths. Create writable directories in advance.
4. Select devices and a sufficient **per-GPU** batch size. The discriminator's unqualified `squeeze` breaks on a local batch of one. A global batch of two over two GPUs can therefore fail. Also account for the final remainder batch.
5. Keep the adversarial branch unless repairing and validating the older non-discriminator branch, which does not match the current loader.

After those preparations, the entry point is:

```bash
python Train_RP_PCN.py
```

This is not a promise that the unedited checkout trains successfully.

| Setting | Actual released behavior |
| --- | --- |
| Input / missing-target points | 2,048 / 2,048 by default |
| Input scales | [2048, 512, 256] |
| Decoder outputs | 128, 256 and `crop_point_num` missing points |
| Batch / epochs | 2 / 151 defaults |
| Adversarial branch | `D_choose=1` |
| Reconstruction / adversarial weight | 0.95 / 0.05 |
| Optimizers | Adam, lr 1e-4, betas (0.9, 0.999), eps 1e-5 |
| Weight decay | 0.001 default |
| Scheduler | StepLR, step 40, gamma 0.2 |

### Options requiring care

- `--learning_rate` and `--beta1` do not set the optimizer values; the optimizer constructors use literals.
- `--ngpu` is not passed as DataParallel device selection.
- `--point_scales_list` uses `type=list`, which converts text to characters, not a numeric list. Do not copy a supposed numeric-list CLI override; adapt the code and validate shapes.
- Three scale branches and `each_scales_size=1` are structurally assumed. Each scale needs at least 20 points for KNN; actual scale lengths must match pooling configuration.
- Fine output count must be positive and divisible by 256 for the decoder reshapes.
- `D_choose=0` still expects two loader outputs; the paired loader returns three. Its older target-scale assumptions also differ.
- `workers=0` is the safer existing setting on Windows until a proper main guard is introduced.

The trainer periodically inspects the **first shuffled test batch**, not a full validation pass. Its best-checkpoint comparison uses the final training batch's generator loss. Saved dictionaries contain `epoch` and `state_dict`, not complete optimizer/scheduler state.

## CSV prediction: Test_csv.py

A compatible checkpoint is required and not bundled. Before running:

- Set `--netG` to that checkpoint; match decoder size and DataParallel state-dictionary keys.
- Edit/remove the assignments that override `opt.infile` and `opt.infile_real`. Passing those flags alone currently has no effect.
- Reconcile sample sizes, the **512 appended zero points**, input scales and the checkpoint.

The supplied `crop4-1.csv` has 1,536 rows; padding makes 2,048, but the default first scale is **4,096**. This default is inconsistent. The decoder default is 1,024 missing points, compared with the trainer's 2,048; the supplied target has 512 rows. Changing a filename alone does not reconcile these settings.

Once adapted and verified:

```bash
python Test_csv.py --netG /path/to/compatible_checkpoint.pth
```

It still reads a target CSV. It saves `<input>_Net.txt` (including zero padding) and `<input>_fake.txt` as comma-separated XYZ beside the input, potentially replacing earlier outputs. The predicted file is the **missing region**, not an automatically merged complete canopy.

## Historical analysis and export

| File | Preparation and limitations |
| --- | --- |
| `show_CD.py` | Fix paths/checkpoint, three-value loader unpacking, and distance values incorrectly used as indices. Its center-crop protocol differs from paired-target training. |
| `show_recon_RPPCN.py` | Set dataset/checkpoint/output paths, create output directory, provide CUDA and compatible shapes; intended export uses the first sample per batch. |
| `self-test/` | Archived ablations with missing imported modules/resources; not a runnable automated test suite. |

These scripts are recorded for provenance; this update does not present them as turnkey evaluation. There is no `evaluate.py` or `visualize_results.py`.

## Reconstruction and data generation

`COLMAP_batch.py` writes and runs temporary Windows batch files in hardcoded image directories. Configure its image folders, conda environment and external Instant-NGP script before execution.

`create_dataset.py` uses hardcoded mesh/output paths and a camera-direction CSV. Verify visibility semantics and required point attributes. The PLY outputs still need explicit conversion/organization into the loader layout and independent split manifests; see [DATA.md](DATA.md).

## Troubleshooting

| Failure | Likely check |
| --- | --- |
| Missing `../dataset/mydata` | Hardcoded roots, not just `--dataroot` |
| Missing model / invalid checkpoint | No pretrained weights are supplied; placeholders are not models |
| CUDA error despite CPU selection | Model/device allocations are hardcoded |
| Pooling/reshape size error | Scale lengths, zero padding, fine-point count and checkpoint architecture |
| Too many values to unpack | Legacy two-value call site versus paired loader's three values |
| Batch-axis / BatchNorm error | Local per-GPU batch size and remainder batch |
| Missing output directory | Configure and create all log/checkpoint/export parents |

For help, report the commit, command, environment, checkpoint provenance and full traceback.
