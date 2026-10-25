"""Batched Qwen3-VL generation using the pinned backend's model, images and sampling.

caption_backend.py stays unchanged so descriptions made one at a time keep their
fingerprints; batched descriptions also record this module's hash (decision 0007).
Running out of GPU memory is a machine limit, not an asset fault: GpuMemoryError
stops the batch and leaves its assets pending.
"""
import time

from .caption_backend import prepare_images
from .config import ConfigError

MODE = 'batched-v1'
POLICY = 'single-attempt-no-fault-retry-batched-v1'


class GpuMemoryError(Exception):
    """Not enough GPU memory for the configured batch size; deliberately not a ValueError."""


def memory_message(size):
    return (f'Not enough GPU memory for description batch size {size}. Lower it in Settings → General, '
            'then process again; completed descriptions are kept and these assets stay pending.')


def generate_batch(backend, inputs_list, prompt, max_new_tokens=1100):
    """Return (raw, metrics) or the exception for each item, in order; one bad item never fails the rest."""
    torch = backend.torch
    results, prepared, conversations = [None] * len(inputs_list), [], []
    for index, inputs in enumerate(inputs_list):
        try:
            images, processed = prepare_images(backend.config, inputs)
        except (OSError, ValueError) as exc:
            results[index] = exc
            continue
        content = []
        for item, image in zip(inputs, images):
            content.extend([{'type': 'text', 'text': 'View: ' + item['view_label']}, {'type': 'image', 'image': image}])
        content.append({'type': 'text', 'text': prompt})
        conversations.append([{'role': 'user', 'content': content}])
        prepared.append((index, len(images), processed))
    if not prepared:
        return results
    started = time.perf_counter()
    try:
        backend.processor.tokenizer.padding_side = 'left'
        tensors = backend.processor.apply_chat_template(conversations, tokenize=True, add_generation_prompt=True,
                                                        return_dict=True, return_tensors='pt', padding=True).to('cuda:0')
        grid = tensors.get('image_grid_thw')
        if grid is None or len(grid) != sum(count for _, count, _ in prepared) or 'pixel_values' not in tensors:
            raise ConfigError('Processor did not consume every actual input image')
        if not bool(torch.isfinite(tensors['pixel_values']).all()):
            raise ConfigError('Invalid/empty pixel tensor')
        torch.manual_seed(backend.settings['seed'])
        with torch.inference_mode():
            outputs = backend.model.generate(**tensors, do_sample=True, num_beams=1, temperature=0.7, top_p=0.8,
                                             top_k=20, repetition_penalty=1.1, max_new_tokens=max_new_tokens,
                                             max_time=120, use_cache=True)
        torch.cuda.synchronize()
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        raise GpuMemoryError(memory_message(len(inputs_list))) from None
    except Exception as exc:  # A batch-wide runtime fault fails every prepared item, without retry.
        for index, _, _ in prepared:
            results[index] = exc
        return results
    elapsed = time.perf_counter() - started
    eos = backend.model.generation_config.eos_token_id
    stops = set(eos if isinstance(eos, (list, tuple)) else [eos])
    width = tensors['input_ids'].shape[1]
    image_token_id = backend.model.config.image_token_id
    grid_rows, offset = grid.tolist(), 0
    resources = backend.resources()
    for row, (index, count, processed) in enumerate(prepared):
        tokens = outputs[row, width:].tolist()
        length = next((i + 1 for i, token in enumerate(tokens) if token in stops), None)
        image_tokens = int((tensors['input_ids'][row] == image_token_id).sum().item())
        item_grid, offset = grid_rows[offset:offset + count], offset + count
        if length is None or image_tokens == 0:
            results[index] = RuntimeError('Invalid/empty pixel tensor' if image_tokens == 0 else
                                          'Generation timed out or exhausted output token limit')
            continue
        text = backend.processor.decode(tokens[:length], skip_special_tokens=True, clean_up_tokenization_spaces=False)
        results[index] = (text, {'elapsed_seconds': elapsed, 'input_tokens': int(tensors['attention_mask'][row].sum()),
                                 'generated_tokens': length, 'image_tokens': image_tokens, 'image_grid_thw': item_grid,
                                 'processed_images': processed, 'max_new_tokens': max_new_tokens,
                                 'batch_assets': len(prepared), 'batch_position': row,
                                 'batch_padded_input_tokens': width, **resources})
    return results
