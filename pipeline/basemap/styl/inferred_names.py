"""Names inferred for .styl stream property ids that have no dedicated kDefault* constant in VectorKit.

Evidence = iOS 26.1 call sites (callers_by_stream_id.tsv), the styles that set the property in globe-default-20207.styl
and the values seen there.  confidence: 'high' = two independent pieces of evidence agree, 'mid' = one, 'low' = values only.
"""
from property_names import PROPS

INFERRED = {
    0:   ('visibleFlag', 'mid', 'bool read by layoutElevatedPolygonMeshes/PolylineOverlayStyle/CoastlineRenderLayer; set#1 {0:False} is what borders use for z0-2 (hidden at globe zoom); polarity unverified'),
    1:   ('fillColor', 'high', 'main colour of 802 sets; Route-Line-Base-Light = rgb(0,162,255) Apple route blue; PropertyID 92 sits right before kDefaultStrokeColor (93)'),
    2:   ('strokeColor', 'high', 'kDefaultStrokeColor'),
    3:   ('width', 'high', 'float read by md::getRoadWidths, RouteLineSection::halfWidthAtZoom; Rivers-Line-Base 1.5..4.0 by zoom'),
    6:   ('strokeWidth', 'high', 'float read by getRoadWidths + writeSourceConstants<Stroke1StyleProperties>; casing width, 0 for most lines'),
    9:   ('roadSignTextSize', 'mid', 'FontSizeInfo::update + GetRoadSignMetadataForStyleQuery; only in RoadSign styles, 21/26/30'),
    13:  ('renderOrder', 'mid', 'uint32 read by RoadBatch::setRenderOrdersForStrokeAndFill; values 5/20/253/254'),
    15:  ('strokeRenderOrder', 'mid', 'uint32 read by setRenderOrdersForStrokeAndFill; values 7/19'),
    16:  ('strokeEnabled', 'low', 'bool read with Stroke1StyleProperties; always True where present'),
    18:  ('textSizeScale', 'mid', 'float read by LabelTextStyleGroup::update; 1541 uses, values 0.5/0.75/1.0 per zoom band'),
    21:  ('fontSize', 'high', 'uint read by LabelStyle::prepareStyleGroup; values 8/12/13/18/20 pt'),
    22:  ('iconName', 'high', 'string: "POI-Marker", "Nav_Label_Annotation_TrafficDelay_Gray", "Settlement..."'),
    23:  ('fontSpec', 'high', 'string: "%$default,semibold,width=90" (family,weight,width)'),
    24:  ('textColor', 'high', 'rgba8 read by LabelCoreStyleGroup::update; Ocean-Label-Color-Dark-Base z2-4 rgb(62,116,182) = measured #3d73b6'),
    25:  ('textHaloColor', 'high', 'kDefaultLabelHaloColor; white a0.7 on road labels'),
    29:  ('fontSizeParam', 'low', 'float read by FontSizeInfo::update; values 0.5/1.2/3.0'),
    30:  ('lineLabelParamA', 'low', 'float read by LabelLineStyleGroup; 10/11 on road styles'),
    31:  ('lineLabelParamB', 'low', 'float read by LabelLineStyleGroup; 9/10/11 on road styles'),
    41:  ('arrowSize', 'mid', 'float only in Route-Line-Arrows / Arrows-* styles; 4/6/7.5/8.3'),
    43:  ('labelPriorityGroup', 'low', 'int32 read by MapStandardLabeler::synchronizedUpdate; 0/-1/1/2'),
    55:  ('coastlineGlowWidth', 'high', 'float read by CoastlineRenderLayer::layout; only Coastline-Glow-* styles; 0/2.5/3/3.25'),
    57:  ('coastlineGlowColor', 'high', 'rgba8 only in Coastline-Glow-* styles; Light rgb(135,221,251) = rendered near-shore band #88d4f5 (acceptance session)'),
    58:  ('sizeRange', 'low', 'floatPair [0,2] on PhysicalFeature-LMZ styles'),
    60:  ('patternBits', 'low', 'uint64 on Border-* / Railway-* styles; bit mask, probably dash/tick pattern'),
    61:  ('patternBits2', 'low', 'uint64 on Railway-Base'),
    90:  ('trafficStyleA', 'mid', 'trafficDecoder composite (4 of them: 90-93) only in Traffic-* styles; layout not decoded'),
    91:  ('trafficStyleB', 'mid', 'see 90'),
    92:  ('trafficStyleC', 'mid', 'see 90'),
    93:  ('trafficStyleD', 'mid', 'see 90'),
    127: ('minFontSize', 'mid', 'float read by FontSizeInfo::update; 9/10 pt'),
    168: ('iconColor', 'mid', 'rgba8 on POI-Route-OnRouteWaypointIcon-*'),
    172: ('labelInfo', 'high', 'labelInfoDecoder composite: presence-flagged label height / height curve / halo size / font expansion / spacing / arrow height; layout not decoded'),
    203: ('gridColor', 'high', 'rgba8 only in Grid-GlobeHybrid (graticule on the hybrid globe)'),
    210: ('routeLineScaleA', 'mid', 'Route-Line-Scale only; read by RouteLineSection::halfWidthAtZoom'),
    211: ('routeLineScaleB', 'mid', 'Route-Line-Scale only'),
    212: ('routeLineScaleC', 'mid', 'Route-Line-Scale only'),
}


def name_of(pid):
    """Best available name for a stream property id: kDefault* constant, else inferred name, else the number."""
    p = PROPS.get(pid)
    if p and p[2]:
        n = p[2].replace('kDefault', '')
        return n[0].lower() + n[1:]
    if pid in INFERRED:
        return INFERRED[pid][0]
    return str(pid)
