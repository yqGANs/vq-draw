import torch
import torch.nn as nn


class Encoder(nn.Module):
    def __init__(self, shape, options, base, loss_fn, output_fn=None, num_stages=0):
        super().__init__()
        self.shape = shape
        self.options = options
        self.base = base
        self.loss_fn = loss_fn
        self.output_layers = []
        self.output_biases = []
        for _ in range(num_stages):
            layer = output_fn()
            bias = nn.Parameter(torch.zeros((options,) + shape))
            self.add_stage(layer, bias)

    def forward(self, inputs):
        """
        Apply the encoder and track the corresponding
        reconstructions.

        Returns:
          A tuple (encodings, reconstructions)
        """
        current_outputs = torch.zeros_like(inputs)
        encodings = []
        for i in range(self.num_stages):
            new_outputs = self.apply_stage(i, current_outputs)
            losses = torch.stack([torch.stack([self.loss_fn(new_outputs[i, j], inputs[i])
                                               for j in range(new_outputs.shape[1])])
                                  for i in range(new_outputs.shape[0])])
            indices = torch.argmin(losses, dim=1)
            encodings.append(indices)
            current_outputs = new_outputs[range(new_outputs.shape[0]), indices]
        if len(encodings) == 0:
            return torch.zeros((inputs.shape[0], 0), dtype=torch.long), current_outputs
        return torch.stack(encodings, dim=-1), current_outputs

    def decode(self, codes):
        current_outputs = torch.zeros((codes.shape[0],) + self.shape, device=codes.device)
        for i in range(self.num_stages):
            new_outputs = self.apply_stage(i, current_outputs)
            current_outputs = new_outputs[:, codes[:, i]]
        return current_outputs

    def reconstruct(self, inputs, batch=None):
        if batch is None:
            return self(inputs)[1]
        results = []
        for i in range(0, inputs.shape[0], batch):
            results.append(self(inputs[i:i+batch])[1])
        return torch.cat(results, dim=0)

    def apply_stage(self, idx, x):
        layer = self.output_layers[idx]
        bias = self.output_biases[idx]
        base_out = self.base(x)
        layer_out = layer(base_out)
        layer_out = bias + layer_out
        return x[:, None] + layer_out

    def add_stage(self, layer, bias):
        i = self.num_stages
        self.output_layers.append(layer)
        self.output_biases.append(bias)
        self.add_module('output%d' % i, layer)
        self.register_parameter('bias%d' % i, bias)

    @property
    def num_stages(self):
        return len(self.output_layers)