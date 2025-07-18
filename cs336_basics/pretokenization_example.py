import os
from typing import BinaryIO,Dict
import multiprocessing as mp 
from collections import defaultdict
import regex as re
PAT = r"""'(?:[sdmt]|ll|ve|re)| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+"""


def find_chunk_boundaries(
    file: BinaryIO, 
    desired_num_chunks: int, 
    split_special_token: bytes
) -> list[int]:
    """
    Chunk the file into parts that can be counted independently.
    May return fewer chunks if the boundaries end up overlapping.
    """
    assert isinstance(split_special_token, bytes), (
        "Must represent special token as a bytestring"
    )

    # Get total file size in bytes
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    chunk_size = file_size // desired_num_chunks

    # Initial guesses for chunk boundary locations, uniformly spaced
    # Chunks start on previous index, don't include last index
    chunk_boundaries = [i * chunk_size for i in range(desired_num_chunks + 1)]
    chunk_boundaries[-1] = file_size

    mini_chunk_size = 4096  # Read ahead by 4k bytes at a time

    for bi in range(1, len(chunk_boundaries) - 1):
        initial_position = chunk_boundaries[bi]
        file.seek(initial_position)  # Start at boundary guess
        while True:
            mini_chunk = file.read(mini_chunk_size)  # Read a mini chunk

            # If EOF, this boundary should be at the end of the file
            if mini_chunk == b"":
                chunk_boundaries[bi] = file_size
                break

            # Find the special token in the mini chunk
            found_at = mini_chunk.find(split_special_token)
            if found_at != -1:
                chunk_boundaries[bi] = initial_position + found_at
                break
            initial_position += mini_chunk_size

    # Make sure all boundaries are unique, but might be fewer than desired_num_chunks
    return sorted(set(chunk_boundaries))


def process_chunk(args):
    '''worker function '''
    filepath, start, end ,split_special_token = args 
    with open(filepath, 'rb') as f: 
        f.seek(start)
        chunk_data= f.read(end-start)
        chunk_text = chunk_data.decode('utf-8',errors='ignore')


        special_tokens=[split_special_token.decode('utf-8',errors='ignore')]



        #prob dont need a list
        escaped_tokens=[re.escape(token) for token in special_tokens]
        split_vocab="|".join(escaped_tokens)
        #has all the documents seperated by special tokens like end of document start of document 
        text_segments = re.split(split_vocab,chunk_text)
        #dictionary to store the presplit tokens /words/whatever is split by PAT
        token_counts=defaultdict(int)

        for segment in text_segments:
            if segment.strip():#non white space 
                #iterare over each word 
                for match in re.finditer(PAT,segment):
                    #get the word
                    token=match.group()
                    if token.strip():
                        token_counts[token]+=1
        return dict(token_counts)
def parallel_pretokenize(file_path:str, num_processes:int = None) -> Dict:
    '''parallel preokenization and return tem merged token counts'''
    if num_processes is None: 
        num_processes= mp.cpu_count()
    
    split_token_bytes= "<|endoftext|>".encode("utf-8")

    with open(file_path,"rb") as f: 
        boundaries= find_chunk_boundaries(f,num_processes,split_token_bytes)
    work_items = [(file_path, start, end, split_token_bytes) 
                  for start, end in zip(boundaries[:-1], boundaries[1:])] 
    with mp.Pool(processes=num_processes) as pool: 
        #assigns function to each worker item(list of args)
        chunk_results=pool.map(process_chunk,work_items)
    #merge 
    final_counts=defaultdict(int)
    for chunk_result in chunk_results: 
        for token, count in chunk_result.items():
            final_counts[token]+=count
    return dict(final_counts)

         




## 
if __name__ == '__main__':
    mp.set_start_method('fork',force=True)

    token_counts=parallel_pretokenize("./data/TinyStoriesV2-GPT4-train.txt", num_processes=8)
    print(mp.cpu_count())

        # Run pre-tokenization on your chunk and store the counts for each pre-token