"""Names inferred for .styl stream property ids that have no dedicated kDefault* constant in VectorKit.

Evidence = iOS 26.1 call sites (callers_by_stream_id.tsv), the styles that set the property in globe-default-20207.styl
and the values seen there.  confidence: 'high' = two independent pieces of evidence agree, 'mid' = one, 'low' = values only.
"""
from property_names import PROPS

INFERRED = {
    0:   ('visible', 'high', 'bool read by layoutElevatedPolygonMeshes/PolylineOverlayStyle/CoastlineRenderLayer; False hides: borders z0-2 {0:False}, Continent-PointLabel-Base z3-24 {0:False} (continent names vanish when zoomed in)'),
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
    90:  ('trafficStopped', 'high', 'trafficDecoder composite; Traffic-on-route-Light-Base fillColor rgb(104,23,37) dark red; order Stopped/Slow/Medium/Fast = kDefaultTrafficFillColorStopped/Slow/Medium/Fast'),
    91:  ('trafficSlow', 'high', 'fillColor rgb(239,56,57) red'),
    92:  ('trafficMedium', 'high', 'fillColor rgb(255,201,23) yellow'),
    93:  ('trafficFast', 'high', 'fillColor rgb(17,151,255) blue on-route / visibility flag set'),
    127: ('minFontSize', 'mid', 'float read by FontSizeInfo::update; 9/10 pt'),
    168: ('iconColor', 'mid', 'rgba8 on POI-Route-OnRouteWaypointIcon-*'),
    172: ('labelInfo', 'high', 'labelInfoDecoder composite, decoded: {height (pt), heightCurve, heightCurveLimit, haloSize, fontExpansion, spacing, arrowHeight}; height is the label text size per zoom band (Country-Label-Extra-Large 13->16->20 pt)'),
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
