"""
GNINA GPU Serverless Handler for RunPod.

Input:
  - receptor_pdb: string (PDB file content)
  - ligand_sdf: string (SDF file content, can contain multiple molecules)
  - center_x, center_y, center_z: float (pocket center)
  - size_x, size_y, size_z: float (box size, default 25)
  - exhaustiveness: int (default 8, increase for better results)
  - num_modes: int (default 9)
  - cnn_scoring: string (default "rescore")
  
Output:
  - results: list of docked molecules with scores
  - elapsed_seconds: float
"""

import runpod
import subprocess
import tempfile
import os
import time
import json
import re


def parse_gnina_sdf(sdf_content):
    """Parse GNINA SDF output into list of results with scores."""
    molecules = []
    blocks = sdf_content.split("$$$$")
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        mol = {"sdf_block": block + "\n$$$$\n"}
        
        # Extract GNINA scores from SDF properties
        for line in block.split("\n"):
            if "> <minimizedAffinity>" in block:
                pass  # handled below
        
        # Parse SDF properties
        lines = block.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("> <"):
                prop_name = line.strip("> <").rstrip(">").strip()
                if i + 1 < len(lines):
                    prop_value = lines[i + 1].strip()
                    try:
                        prop_value = float(prop_value)
                    except ValueError:
                        pass
                    mol[prop_name] = prop_value
            i += 1
        
        if mol.get("minimizedAffinity") is not None or mol.get("CNNscore") is not None:
            molecules.append(mol)
    
    return molecules


def run_gnina(job_input):
    """Run GNINA docking on GPU."""
    start_time = time.time()
    
    receptor_pdb = job_input["receptor_pdb"]
    ligand_sdf = job_input["ligand_sdf"]
    
    center_x = job_input.get("center_x", 0)
    center_y = job_input.get("center_y", 0)
    center_z = job_input.get("center_z", 0)
    size_x = job_input.get("size_x", 25)
    size_y = job_input.get("size_y", 25)
    size_z = job_input.get("size_z", 25)
    exhaustiveness = job_input.get("exhaustiveness", 8)
    num_modes = job_input.get("num_modes", 9)
    cnn_scoring = job_input.get("cnn_scoring", "rescore")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        receptor_path = os.path.join(tmpdir, "receptor.pdb")
        ligand_path = os.path.join(tmpdir, "ligands.sdf")
        output_path = os.path.join(tmpdir, "docked.sdf")
        log_path = os.path.join(tmpdir, "gnina.log")
        
        # Write input files
        with open(receptor_path, "w") as f:
            f.write(receptor_pdb)
        with open(ligand_path, "w") as f:
            f.write(ligand_sdf)
        
        # Build GNINA command
        cmd = [
            "gnina",
            "--receptor", receptor_path,
            "--ligand", ligand_path,
            "--out", output_path,
            "--center_x", str(center_x),
            "--center_y", str(center_y),
            "--center_z", str(center_z),
            "--size_x", str(size_x),
            "--size_y", str(size_y),
            "--size_z", str(size_z),
            "--exhaustiveness", str(exhaustiveness),
            "--num_modes", str(num_modes),
            "--cnn_scoring", cnn_scoring,
            "--cnn", "crossdock_default2018",
        ]
        
        # Run GNINA
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour max
            )
            
            stderr = result.stderr
            stdout = result.stdout
            
            if result.returncode != 0:
                return {
                    "error": f"GNINA failed (code {result.returncode})",
                    "stderr": stderr[-2000:] if stderr else "",
                    "stdout": stdout[-1000:] if stdout else "",
                    "elapsed_seconds": time.time() - start_time
                }
            
            # Read output
            if not os.path.exists(output_path):
                return {
                    "error": "GNINA produced no output file",
                    "stderr": stderr[-2000:] if stderr else "",
                    "elapsed_seconds": time.time() - start_time
                }
            
            with open(output_path, "r") as f:
                docked_sdf = f.read()
            
            # Parse results
            molecules = parse_gnina_sdf(docked_sdf)
            
            # Build compact results (without full SDF to save bandwidth)
            compact_results = []
            for i, mol in enumerate(molecules):
                compact_results.append({
                    "rank": i + 1,
                    "minimizedAffinity": mol.get("minimizedAffinity"),
                    "CNNscore": mol.get("CNNscore"),
                    "CNNaffinity": mol.get("CNNaffinity"),
                })
            
            elapsed = time.time() - start_time
            
            return {
                "results": compact_results,
                "docked_sdf": docked_sdf,
                "n_molecules": len(molecules),
                "elapsed_seconds": round(elapsed, 2),
                "gnina_stdout": stdout[-500:] if stdout else "",
                "gpu_used": True
            }
            
        except subprocess.TimeoutExpired:
            return {
                "error": "GNINA timed out after 3600 seconds",
                "elapsed_seconds": time.time() - start_time
            }
        except Exception as e:
            return {
                "error": str(e),
                "elapsed_seconds": time.time() - start_time
            }


def handler(job):
    """RunPod serverless handler."""
    job_input = job["input"]
    
    # Validate required fields
    required = ["receptor_pdb", "ligand_sdf", "center_x", "center_y", "center_z"]
    for field in required:
        if field not in job_input:
            return {"error": f"Missing required field: {field}"}
    
    return run_gnina(job_input)


# Start RunPod serverless worker
runpod.serverless.start({"handler": handler})
