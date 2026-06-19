"""LoRA fine-tune path — cheap, one-time finance specialization.

The honest "specialize the model" move (NOT from-scratch): low-rank adaptation of a small
open model on a finance instruction set. `prepare_data` builds the dataset from the
grounded corpus; `train` runs it free + locally on Apple Silicon via mlx-lm (or prints the
command). See README.md for cost notes and how to scale the dataset.
"""
