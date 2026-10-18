"""PyMOL pocket render of the 3PTB crystal (benzamidine) for film C. Usage: .venv/bin/python render_3ptb.py"""
from pymol import cmd
cmd.reinitialize()
cmd.set("ray_opaque_background", 1); cmd.bg_color("white"); cmd.set("ray_shadows", 0); cmd.set("antialias", 2)
cmd.set("cartoon_transparency", 0.55); cmd.set("stick_radius", 0.26)
cmd.load("/home/user/harness-hackathon/tests/fixtures/sources/3PTB.cif", "xtal")
cmd.remove("hydro or solvent")
cmd.hide("everything")
cmd.show("cartoon", "polymer"); cmd.color("0xC7D8CC", "polymer")
lig = "resn BEN"
pocket = "byres (polymer and not name N+C+O) within 4.5 of (resn BEN)"
cmd.show("sticks", pocket + " and sidechain"); cmd.set("stick_radius", 0.14, "polymer")
cmd.color("0x9A9A92", pocket + " and elem C"); cmd.util.cnc(pocket)
cmd.show("spheres", "resn CA"); cmd.set("sphere_scale", 0.45)
cmd.show("sticks", lig); cmd.color("0xB07E2C", lig + " and elem C"); cmd.util.cnc(lig)
cmd.orient(lig); cmd.zoom(lig, 7.0)
cmd.png("/home/user/harness-hackathon/out/videos/c/live/3ptb_pocket.png", width=960, height=720, dpi=150, ray=1)
