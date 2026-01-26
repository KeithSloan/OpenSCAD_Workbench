from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.processAST import flatten_hull_minkowski_node
from freecad.OpenSCAD_Ext.parsers.csg_parser.processAST import generate_stl_from_scad

import threading
import queue
import Mesh

# -----------------------------
# multi processing functions
# -----------------------------

# Flatten node to SCAD string
# scad_str = flatten_hull_minkowski_node(node, indent=4)

# Generate STL via OpenSCAD CLI
# stl_file = generate_stl_from_scad(scad_str)

import threading
import queue
import itertools
import heapq
import Mesh


def process_waiter(popen, stl_file, que):
    """
    Wait for a subprocess to finish and report its STL file.
    """
    try:
        popen.wait()
    finally:
        que.put(stl_file)


def multi_hull(node):
    """
    Start all OpenSCAD jobs immediately.
    Merge meshes as soon as two finished meshes are available.
    Always merge the two smallest meshes first (by facet count).
    """

    results = queue.Queue()
    mesh_heap = []
    counter = itertools.count()

    children = list(getattr(node, "children", []))
    total_jobs = len(children)
    finished_jobs = 0

    # --- Start ALL jobs ---
    for child in children:
        scad_str = flatten_hull_minkowski_node(child, indent=4)
        popen, stl_file = generate_stl_from_scad(scad_str)

        threading.Thread(
            target=process_waiter,
            args=(popen, stl_file, results),
            daemon=True
        ).start()

    # --- Streaming merge loop ---
    while finished_jobs < total_jobs:

        # Block until one job finishes
        stl_file = results.get()
        finished_jobs += 1

        mesh = Mesh.Mesh(stl_file)

        # Push mesh into heap (facet_count, tie_breaker, mesh)
        heapq.heappush(
            mesh_heap,
            (mesh.CountFacets, next(counter), mesh)
        )

        # Merge while possible
        while len(mesh_heap) >= 2:
            _, _, m1 = heapq.heappop(mesh_heap)
            _, _, m2 = heapq.heappop(mesh_heap)

            merged = Mesh.Mesh()
            merged.addMesh(m1)
            merged.addMesh(m2)

            heapq.heappush(
                mesh_heap,
                (merged.CountFacets, next(counter), merged)
            )

    # --- Final collapse (safety) ---
    while len(mesh_heap) > 1:
        _, _, m1 = heapq.heappop(mesh_heap)
        _, _, m2 = heapq.heappop(mesh_heap)

        merged = Mesh.Mesh()
        merged.addMesh(m1)
        merged.addMesh(m2)

        heapq.heappush(
            mesh_heap,
            (merged.CountFacets, next(counter), merged)
        )

    return heapq.heappop(mesh_heap)[2]
