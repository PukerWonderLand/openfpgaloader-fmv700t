# Build the SPI-over-JTAG bridge for the XC7VX690T in FFG1927, from
# openFPGALoader's own RTL.
#
# The bridge RTL is not copied here on purpose -- it belongs to (and evolves
# with) the openFPGALoader project. Point this script at a checkout.
#
# Usage:
#   vivado -mode batch -source soj/build.tcl -tclargs /path/to/openFPGALoader/spiOverJtag
#
# Optional 2nd arg overrides the Vivado part (default xc7vx690tffg1927-2):
#   vivado -mode batch -source soj/build.tcl -tclargs <rtl_dir> xc7vx690tffg1927-1
#
# Output: <cwd>/spiOverJtag_xc7vx690tffg1927.bit

set rtl_dir [lindex $argv 0]
if {$rtl_dir eq ""} {
    puts "usage: vivado -mode batch -source soj/build.tcl -tclargs <openFPGALoader/spiOverJtag dir> \[part\]"
    exit 1
}
set part [lindex $argv 1]
if {$part eq ""} {
    set part xc7vx690tffg1927-2
}

set here [file dirname [file normalize [info script]]]
set proj [pwd]/soj_proj
set xdc  [file normalize $here/constr_xc7v_ffg1927.xdc]

file delete -force $proj
create_project -force proj $proj -part $part
add_files -norecurse [list $rtl_dir/xilinx_spiOverJtag.v $rtl_dir/spiOverJtag_core.v]
add_files -fileset constrs_1 -norecurse $xdc
set_property verilog_define {virtex7} [current_fileset]
set_property top spiOverJtag [current_fileset]
puts "SETUP_OK part=$part"

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
puts "RUN_STATUS=[get_property STATUS [get_runs impl_1]]"

set bit $proj/proj.runs/impl_1/spiOverJtag.bit
if {[file exists $bit]} {
    set out [pwd]/spiOverJtag_xc7vx690tffg1927.bit
    file copy -force $bit $out
    puts "BIT=$out"
} else {
    puts "ERROR: no bitstream produced (see the Vivado log)"
    exit 1
}
