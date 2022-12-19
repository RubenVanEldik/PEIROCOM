# Download all bidding zone files
for scenario in "ERAA 2025" "ERAA 2030"
do
  mkdir -p "/app/input/scenarios/${scenario}/bidding_zones"
  cd "/app/input/scenarios/${scenario}/bidding_zones"
  for bidding_zone in AL00 AT00 BA00 BE00 BG00 CH00 CY00 CZ00 DE00 DKE1 DKW1 EE00 ES00 FI00 FR00 FR15 GR00 GR03 HR00 HU00 IE00 ITCA ITCN ITCS ITN1 ITS1 ITSA ITSI LT00 LUB1 LUF1 LUG1 LV00 ME00 MK00 MT00 NL00 NOM1 NON1 NOS0 PL00 PT00 RO00 RS00 SE01 SE02 SE03 SE04 SI00 SK00 TR00 UA01 UK00 UKNI
  do
    wget "${INPUT_DATA_URL}/${scenario//[ ]/_}/bidding_zones/${bidding_zone}.csv"
  done
done

# Download all interconnection files
for scenario in "ERAA 2025" "ERAA 2030"
do
  mkdir -p "/app/input/scenarios/${scenario}/interconnections"
  cd "/app/input/scenarios/${scenario}/interconnections"
  for interconnection_type in hvac hvdc limits
  do
    wget "${INPUT_DATA_URL}/${scenario//[ ]/_}/interconnections/${interconnection_type}.csv"
  done
done
