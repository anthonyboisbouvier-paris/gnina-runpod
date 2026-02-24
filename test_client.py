"""
GNINA RunPod Client - Test script.

Usage:
  python test_client.py --api-key YOUR_RUNPOD_API_KEY --endpoint-id YOUR_ENDPOINT_ID

Or set env vars:
  RUNPOD_API_KEY=...
  GNINA_ENDPOINT_ID=...
"""

import requests
import time
import json
import os
import argparse


# Mini test PDB (just a few atoms for testing)
TEST_RECEPTOR_PDB = """HEADER    TEST RECEPTOR
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.009   1.420   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       1.246   2.390   0.000  1.00  0.00           O
END
"""

# Mini test SDF (aspirin-like)
TEST_LIGAND_SDF = """aspirin
     RDKit          3D

 13 13  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2124    0.6998    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2124    2.0994    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    2.7992    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.2124    2.0994    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.2124    0.6998    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.4249    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    3.6373    0.6998    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.6373    2.0994    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    4.8497    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    4.1988    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.0000    4.8000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
   -1.0000    4.8000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  2  0
  2  3  1  0
  3  4  2  0
  4  5  1  0
  5  6  2  0
  6  1  1  0
  2  7  1  0
  7  8  1  0
  8  9  2  0
  8 10  1  0
  4 11  1  0
 11 12  2  0
 11 13  1  0
M  END
$$$$
"""


def submit_job(api_key, endpoint_id, receptor_pdb, ligand_sdf,
               center_x=0, center_y=0, center_z=0):
    """Submit a GNINA docking job to RunPod."""
    url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    payload = {
        "input": {
            "receptor_pdb": receptor_pdb,
            "ligand_sdf": ligand_sdf,
            "center_x": center_x,
            "center_y": center_y,
            "center_z": center_z,
            "size_x": 25,
            "size_y": 25,
            "size_z": 25,
            "exhaustiveness": 8,
            "num_modes": 3,
            "cnn_scoring": "rescore"
        }
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()


def poll_status(api_key, endpoint_id, job_id, timeout=300):
    """Poll for job completion."""
    url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        status = data.get("status")
        
        print(f"  Status: {status} ({time.time()-start:.0f}s)")
        
        if status == "COMPLETED":
            return data.get("output")
        elif status == "FAILED":
            return {"error": data.get("error", "Unknown failure")}
        
        time.sleep(5)
    
    return {"error": "Timeout waiting for job"}


def main():
    parser = argparse.ArgumentParser(description="Test GNINA RunPod endpoint")
    parser.add_argument("--api-key", default=os.environ.get("RUNPOD_API_KEY"))
    parser.add_argument("--endpoint-id", default=os.environ.get("GNINA_ENDPOINT_ID"))
    parser.add_argument("--receptor", help="Path to receptor PDB file")
    parser.add_argument("--ligand", help="Path to ligand SDF file")
    parser.add_argument("--cx", type=float, default=0, help="Center X")
    parser.add_argument("--cy", type=float, default=0, help="Center Y")
    parser.add_argument("--cz", type=float, default=0, help="Center Z")
    args = parser.parse_args()
    
    if not args.api_key:
        print("ERROR: Set RUNPOD_API_KEY or use --api-key")
        return
    if not args.endpoint_id:
        print("ERROR: Set GNINA_ENDPOINT_ID or use --endpoint-id")
        return
    
    # Load files or use test data
    if args.receptor:
        with open(args.receptor) as f:
            receptor = f.read()
    else:
        receptor = TEST_RECEPTOR_PDB
        print("Using test receptor (mini PDB)")
    
    if args.ligand:
        with open(args.ligand) as f:
            ligand = f.read()
    else:
        ligand = TEST_LIGAND_SDF
        print("Using test ligand (aspirin-like)")
    
    # Submit
    print(f"\nSubmitting GNINA job to RunPod endpoint {args.endpoint_id}...")
    result = submit_job(args.api_key, args.endpoint_id, receptor, ligand,
                        args.cx, args.cy, args.cz)
    job_id = result["id"]
    print(f"Job submitted: {job_id}")
    
    # Poll
    print("\nWaiting for results...")
    output = poll_status(args.api_key, args.endpoint_id, job_id)
    
    if "error" in output:
        print(f"\nERROR: {output['error']}")
    else:
        print(f"\nSUCCESS!")
        print(f"  Molecules docked: {output.get('n_molecules', '?')}")
        print(f"  Time: {output.get('elapsed_seconds', '?')}s")
        print(f"  GPU used: {output.get('gpu_used', '?')}")
        
        if output.get("results"):
            print(f"\n  Results:")
            for r in output["results"]:
                print(f"    #{r['rank']}: Vina={r.get('minimizedAffinity','?')} "
                      f"CNNscore={r.get('CNNscore','?')} "
                      f"CNNaffinity={r.get('CNNaffinity','?')}")
    
    print(f"\nFull output saved to gnina_result.json")
    with open("gnina_result.json", "w") as f:
        json.dump(output, f, indent=2)


if __name__ == "__main__":
    main()
