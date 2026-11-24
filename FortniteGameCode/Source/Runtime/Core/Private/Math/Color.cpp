// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Math/Color.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.
// The colour constants (FLinearColor::Black, FColor::White, ...) are declared only.

#define FNGC_CORE_MATH_EXTRAS 1   // FDateTime, FColor, FVector4, ... (MathDecls.h)
#include "FortniteGameCode/MathDecls.h"

/**
* Helper used by FColor -> FLinearColor conversion. We don't use a lookup table as unlike pow, multiplication is fast.
*/
static const float OneOver255 = 1.0f / 255.0f;

//	FColor->FLinearColor conversion.
// Original FortniteClient-Win64-Shipping.exe: RVA 0x01157720 (end 0x01157762), no .pdata (leaf)
// Original VA: 0x0000000141157720 | File offset: 0x01156D20
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execConv_ColorToLinearColor; sRGBToLinearTable lookups and A * (1/255).
//   FromSRGBColor's body is identical; no other copy of it is in the reference (/OPT:ICF).
FLinearColor::FLinearColor(const FColor& Color)
{
	R = sRGBToLinearTable[Color.R];
	G = sRGBToLinearTable[Color.G];
	B =	sRGBToLinearTable[Color.B];
	A =	float(Color.A) * OneOver255;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01157770 (end 0x0115778B), no .pdata (leaf)
// Original VA: 0x0000000141157770 | File offset: 0x01156D70
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execConv_VectorToLinearColor; R, G, B from the vector and A = 1.
FLinearColor::FLinearColor(const FVector& Vector) :
	R(Vector.X),
	G(Vector.Y),
	B(Vector.Z),
	A(1.0f)
{}

/** Quantizes the linear color and returns the result as a FColor with optional sRGB conversion and quality as goal. */
// Original FortniteClient-Win64-Shipping.exe: RVA 0x01181B30 (end 0x01181CFF)
// Original VA: 0x0000000141181B30 | File offset: 0x01181130
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execConv_LinearColorToColor and FColor::MakeRandomColor; powf(x, 1/2.4) sRGB curve.
FColor FLinearColor::ToFColor(const bool bSRGB) const
{
	float FloatR = FMath::Clamp(R, 0.0f, 1.0f);
	float FloatG = FMath::Clamp(G, 0.0f, 1.0f);
	float FloatB = FMath::Clamp(B, 0.0f, 1.0f);
	float FloatA = FMath::Clamp(A, 0.0f, 1.0f);

	if(bSRGB)
	{
		FloatR = FloatR <= 0.0031308f ? FloatR * 12.92f : FMath::Pow( FloatR, 1.0f / 2.4f ) * 1.055f - 0.055f;
		FloatG = FloatG <= 0.0031308f ? FloatG * 12.92f : FMath::Pow( FloatG, 1.0f / 2.4f ) * 1.055f - 0.055f;
		FloatB = FloatB <= 0.0031308f ? FloatB * 12.92f : FMath::Pow( FloatB, 1.0f / 2.4f ) * 1.055f - 0.055f;
	}

	FColor ret;

	ret.A = FMath::FloorToInt(FloatA * 255.999f);
	ret.R = FMath::FloorToInt(FloatR * 255.999f);
	ret.G = FMath::FloorToInt(FloatG * 255.999f);
	ret.B = FMath::FloorToInt(FloatB * 255.999f);

	return ret;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0117C660 (end 0x0117C70C), no .pdata (leaf)
// Original VA: 0x000000014117C660 | File offset: 0x0117BC60
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: four truncations of channel * 255 clamped to 0..255.
FColor FLinearColor::Quantize() const
{
	return FColor(
		(uint8)FMath::Clamp<int32>(FMath::TruncToInt(R*255.f),0,255),
		(uint8)FMath::Clamp<int32>(FMath::TruncToInt(G*255.f),0,255),
		(uint8)FMath::Clamp<int32>(FMath::TruncToInt(B*255.f),0,255),
		(uint8)FMath::Clamp<int32>(FMath::TruncToInt(A*255.f),0,255)
		);
}

// Convert from RGBE to float as outlined in Gregory Ward's Real Pixels article, Graphics Gems II, page 80.
// Original FortniteClient-Win64-Shipping.exe: RVA 0x01171260 (end 0x011712FA)
// Original VA: 0x0000000141171260 | File offset: 0x01170860
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: ldexp(1/255.0, A - 128) scale, FLinearColor::Black for A == 0; sorts before HSVToLinearRGB.
FLinearColor FColor::FromRGBE() const
{
	if( A == 0 )
		return FLinearColor::Black;
	else
	{
		const float Scale = ldexp( 1 / 255.0, A - 128 );
		return FLinearColor( R * Scale, G * Scale, B * Scale, 1.0f );
	}
}

/**
 * Converts byte hue-saturation-brightness to floating point red-green-blue.
 */
// Original FortniteClient-Win64-Shipping.exe: RVA 0x0116D3B0 (end 0x0116D580)
// Original VA: 0x000000014116D3B0 | File offset: 0x0116C9B0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by FLinearColor::MakeRandomColor (0x01178030); hue ramps over 85 and 84.
FLinearColor FLinearColor::FGetHSV( uint8 H, uint8 S, uint8 V )
{
	float Brightness = V * 1.4f / 255.f;
	Brightness *= 0.7f/(0.01f + FMath::Sqrt(Brightness));
	Brightness  = FMath::Clamp(Brightness,0.f,1.f);
	const FVector Hue = (H<86) ? FVector((85-H)/85.f,(H-0)/85.f,0) : (H<171) ? FVector(0,(170-H)/85.f,(H-85)/85.f) : FVector((H-170)/85.f,0,(255-H)/84.f);
	const FVector ColorVector = (Hue + S/255.f * (FVector(1,1,1) - Hue)) * Brightness;
	return FLinearColor(ColorVector.X,ColorVector.Y,ColorVector.Z,1);
}

/** Converts a linear space RGB color to an HSV color */
// Original FortniteClient-Win64-Shipping.exe: RVA 0x011759D0 (end 0x01175B2D)
// Original VA: 0x00000001411759D0 | File offset: 0x01174FD0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called twice by LerpUsingHSV (0x01175860); sorts after it.
FLinearColor FLinearColor::LinearRGBToHSV() const
{
	const float RGBMin = FMath::Min3(R, G, B);
	const float RGBMax = FMath::Max3(R, G, B);
	const float RGBRange = RGBMax - RGBMin;

	const float Hue = (RGBMax == RGBMin ? 0.0f :
					   RGBMax == R    ? FMath::Fmod((((G - B) / RGBRange) * 60.0f) + 360.0f, 360.0f) :
					   RGBMax == G    ?             (((B - R) / RGBRange) * 60.0f) + 120.0f :
					   RGBMax == B    ?             (((R - G) / RGBRange) * 60.0f) + 240.0f :
					   0.0f);

	const float Saturation = (RGBMax == 0.0f ? 0.0f : RGBRange / RGBMax);
	const float Value = RGBMax;

	// In the new color, R = H, G = S, B = V, A = A
	return FLinearColor(Hue, Saturation, Value, A);
}

/** Converts an HSV color to a linear space RGB color */
// Original FortniteClient-Win64-Shipping.exe: RVA 0x01174F10 (end 0x0117507D)
// Original VA: 0x0000000141174F10 | File offset: 0x01174510
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by LerpUsingHSV (0x01175860); floorf of Hue / 60 and the 6x3 swizzle table.
FLinearColor FLinearColor::HSVToLinearRGB() const
{
	// In this color, R = H, G = S, B = V
	const float Hue = R;
	const float Saturation = G;
	const float Value = B;

	const float HDiv60 = Hue / 60.0f;
	const float HDiv60_Floor = floorf(HDiv60);
	const float HDiv60_Fraction = HDiv60 - HDiv60_Floor;

	const float RGBValues[4] = {
		Value,
		Value * (1.0f - Saturation),
		Value * (1.0f - (HDiv60_Fraction * Saturation)),
		Value * (1.0f - ((1.0f - HDiv60_Fraction) * Saturation)),
	};
	const uint32 RGBSwizzle[6][3] = {
		{0, 3, 1},
		{2, 0, 1},
		{1, 0, 3},
		{1, 2, 0},
		{3, 1, 0},
		{0, 1, 2},
	};
	const uint32 SwizzleIndex = ((uint32)HDiv60_Floor) % 6;

	return FLinearColor(RGBValues[RGBSwizzle[SwizzleIndex][0]],
						RGBValues[RGBSwizzle[SwizzleIndex][1]],
						RGBValues[RGBSwizzle[SwizzleIndex][2]],
						A);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01175860 (end 0x011759C7)
// Original VA: 0x0000000141175860 | File offset: 0x01174E60
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execLinearColorLerpUsingHSV; LinearRGBToHSV twice, Fmod, HSVToLinearRGB.
FLinearColor FLinearColor::LerpUsingHSV( const FLinearColor& From, const FLinearColor& To, const float Progress )
{
	const FLinearColor FromHSV = From.LinearRGBToHSV();
	const FLinearColor ToHSV = To.LinearRGBToHSV();

	float FromHue = FromHSV.R;
	float ToHue = ToHSV.R;

	// Take the shortest path to the new hue
	if( FMath::Abs( FromHue - ToHue ) > 180.0f )
	{
		if( ToHue > FromHue )
		{
			FromHue += 360.0f;
		}
		else
		{
			ToHue += 360.0f;
		}
	}

	float NewHue = FMath::Lerp( FromHue, ToHue, Progress );

	NewHue = FMath::Fmod( NewHue, 360.0f );
	if( NewHue < 0.0f )
	{
		NewHue += 360.0f;
	}

	const float NewSaturation = FMath::Lerp( FromHSV.G, ToHSV.G, Progress );
	const float NewValue = FMath::Lerp( FromHSV.B, ToHSV.B, Progress );
	FLinearColor Interpolated = FLinearColor( NewHue, NewSaturation, NewValue ).HSVToLinearRGB();

	const float NewAlpha = FMath::Lerp( From.A, To.A, Progress );
	Interpolated.A = NewAlpha;

	return Interpolated;
}

/**
* Makes a random but quite nice color.
*/
// Original FortniteClient-Win64-Shipping.exe: RVA 0x01178030 (end 0x0117806A)
// Original VA: 0x0000000141178030 | File offset: 0x01177630
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FMath::FRand (rand), then FGetHSV(Hue, 0, 255); called by FColor::MakeRandomColor.
FLinearColor FLinearColor::MakeRandomColor()
{
	const uint8 Hue = (uint8)(FMath::FRand()*255.f);
	return FLinearColor::FGetHSV(Hue, 0, 255);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01177FE0 (end 0x0117802C)
// Original VA: 0x0000000141177FE0 | File offset: 0x011775E0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FLinearColor::MakeRandomColor (0x01178030), then ToFColor(true) (0x01181B30).
FColor FColor::MakeRandomColor()
{
	return FLinearColor::MakeRandomColor().ToFColor(true);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01177E40 (end 0x01177FD2)
// Original VA: 0x0000000141177E40 | File offset: 0x01177440
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the Planckian-locus constants of Color.cpp; sorts before MakeRandomColor.
FLinearColor FLinearColor::MakeFromColorTemperature( float Temp )
{
	Temp = FMath::Clamp( Temp, 1000.0f, 15000.0f );

	// Approximate Planckian locus in CIE 1960 UCS
	float u = ( 0.860117757f + 1.54118254e-4f * Temp + 1.28641212e-7f * Temp*Temp ) / ( 1.0f + 8.42420235e-4f * Temp + 7.08145163e-7f * Temp*Temp );
	float v = ( 0.317398726f + 4.22806245e-5f * Temp + 4.20481691e-8f * Temp*Temp ) / ( 1.0f - 2.89741816e-5f * Temp + 1.61456053e-7f * Temp*Temp );

	float x = 3.0f * u / ( 2.0f * u - 8.0f * v + 4.0f );
	float y = 2.0f * v / ( 2.0f * u - 8.0f * v + 4.0f );
	float z = 1.0f - x - y;

	float Y = 1.0f;
	float X = Y/y * x;
	float Z = Y/y * z;

	// XYZ to RGB with BT.709 primaries
	float R =  3.2404542f * X + -1.5371385f * Y + -0.4985314f * Z;
	float G = -0.9692660f * X +  1.8760108f * Y +  0.0415560f * Z;
	float B =  0.0556434f * X + -0.2040259f * Y +  1.0572252f * Z;

	return FLinearColor(R,G,B);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01178070 (end 0x011780D4), no .pdata (leaf)
// Original VA: 0x0000000141178070 | File offset: 0x01177670
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: two clamps of (1 - Scalar) / 0.5 and Scalar / 0.5 scaled by 255; sorts after MakeRandomColor.
FColor FColor::MakeRedToGreenColorFromScalar(float Scalar)
{
	float RedSclr = FMath::Clamp<float>((1.0f - Scalar)/0.5f,0.f,1.f);
	float GreenSclr = FMath::Clamp<float>((Scalar/0.5f),0.f,1.f);
	int32 R = FMath::TruncToInt(255 * RedSclr);
	int32 G = FMath::TruncToInt(255 * GreenSclr);
	int32 B = 0;
	return FColor(R, G, B);
}

// Original data: RVA 0x04369F00 (.data, 1024 bytes), read from the reference.
// FMath::Pow( i / 255.f, 2.2f )
float FLinearColor::Pow22OneOver255Table[256] =
{
	0.0f, 5.07705181e-06f, 2.33280043e-05f, 5.69217664e-05f, 0.000107187363f, 0.000175123976f, 0.000261543755f, 0.000367136265f,
	0.000492503808f, 0.000638182857f, 0.000804658514f, 0.000992374262f, 0.00120173953f, 0.00143313454f, 0.00168691529f, 0.00196341611f,
	0.0022629532f, 0.00258582551f, 0.00293231825f, 0.00330270315f, 0.00369723956f, 0.00411617709f, 0.00455975486f, 0.0050282036f,
	0.00552174496f, 0.00604059361f, 0.00658495724f, 0.00715503702f, 0.00775102759f, 0.00837311801f, 0.00902149174f, 0.00969632901f,
	0.0103978021f, 0.0111260824f, 0.0118813347f, 0.0126637202f, 0.0134733971f, 0.0143105192f, 0.0151752383f, 0.0160677005f,
	0.0169880521f, 0.0179364327f, 0.0189129841f, 0.0199178383f, 0.0209511314f, 0.0220129956f, 0.0231035557f, 0.0242229421f,
	0.0253712777f, 0.0265486836f, 0.0277552791f, 0.028991187f, 0.0302565191f, 0.0315513909f, 0.0328759179f, 0.0342302062f,
	0.0356143713f, 0.0370285138f, 0.0384727456f, 0.0399471708f, 0.04145189f, 0.0429870114f, 0.044552628f, 0.0461488441f,
	0.0477757528f, 0.0494334586f, 0.0511220507f, 0.0528416261f, 0.0545922779f, 0.0563740991f, 0.0581871793f, 0.0600316077f,
	0.061907474f, 0.063814871f, 0.0657538772f, 0.067724593f, 0.0697270855f, 0.0717614517f, 0.0738277659f, 0.0759261176f,
	0.0780565888f, 0.0802192613f, 0.0824142024f, 0.0846415088f, 0.086901255f, 0.089193508f, 0.0915183499f, 0.0938758701f,
	0.0962661207f, 0.0986891985f, 0.101145163f, 0.103634097f, 0.106156066f, 0.108711153f, 0.111299418f, 0.113920934f,
	0.116575778f, 0.119264014f, 0.121985711f, 0.124740943f, 0.127529785f, 0.130352274f, 0.133208513f, 0.136098549f,
	0.139022455f, 0.14198029f, 0.144972131f, 0.14799802f, 0.151058048f, 0.154152259f, 0.157280728f, 0.160443515f,
	0.163640678f, 0.166872278f, 0.170138374f, 0.173439041f, 0.176774323f, 0.180144295f, 0.183549002f, 0.186988503f,
	0.190462872f, 0.19397217f, 0.197516426f, 0.20109573f, 0.204710126f, 0.208359659f, 0.212044403f, 0.215764403f,
	0.219519719f, 0.223310411f, 0.227136523f, 0.230998129f, 0.234895259f, 0.238827989f, 0.242796347f, 0.246800423f,
	0.250840247f, 0.254915863f, 0.259027332f, 0.263174713f, 0.267358065f, 0.271577418f, 0.275832832f, 0.280124366f,
	0.284452051f, 0.288815975f, 0.293216139f, 0.297652632f, 0.302125484f, 0.306634754f, 0.311180502f, 0.315762758f,
	0.320381552f, 0.325036973f, 0.329729021f, 0.334457815f, 0.339223325f, 0.344025671f, 0.348864824f, 0.353740901f,
	0.358653903f, 0.36360389f, 0.368590921f, 0.373615026f, 0.378676265f, 0.383774638f, 0.388910264f, 0.394083112f,
	0.399293303f, 0.404540837f, 0.409825742f, 0.415148079f, 0.420507938f, 0.425905287f, 0.431340218f, 0.436812758f,
	0.44232294f, 0.447870851f, 0.453456461f, 0.459079891f, 0.464741141f, 0.470440239f, 0.476177275f, 0.48195225f,
	0.487765193f, 0.493616194f, 0.499505281f, 0.505432487f, 0.511397839f, 0.517401397f, 0.523443162f, 0.529523194f,
	0.535641611f, 0.541798353f, 0.547993481f, 0.554227114f, 0.560499132f, 0.566809714f, 0.57315886f, 0.57954663f,
	0.585972965f, 0.592438042f, 0.598941803f, 0.605484307f, 0.612065613f, 0.618685722f, 0.625344694f, 0.632042646f,
	0.638779461f, 0.645555258f, 0.652370095f, 0.659223974f, 0.666116953f, 0.673049092f, 0.680020332f, 0.687030792f,
	0.694080532f, 0.701169491f, 0.708297789f, 0.715465426f, 0.722672462f, 0.729918897f, 0.73720479f, 0.744530201f,
	0.75189507f, 0.759299576f, 0.7667436f, 0.774227321f, 0.781750679f, 0.789313734f, 0.796916544f, 0.804559112f,
	0.812241495f, 0.819963694f, 0.827725768f, 0.835527778f, 0.843369722f, 0.851251662f, 0.859173596f, 0.867135525f,
	0.875137568f, 0.883179724f, 0.891262054f, 0.899384499f, 0.907547176f, 0.915750146f, 0.923993349f, 0.932276845f,
	0.940600693f, 0.948964953f, 0.957369566f, 0.96581465f, 0.974300206f, 0.982826233f, 0.991392851f, 1.0f,
};

// Original data: RVA 0x0436A300 (.data, 1024 bytes), read from the reference.
// sRGB to linear for i / 255.f
float FLinearColor::sRGBToLinearTable[256] =
{
	0.0f, 0.000303526991f, 0.000607053982f, 0.000910580973f, 0.00121410796f, 0.00151763496f, 0.00182116195f, 0.00212468882f,
	0.00242821593f, 0.0027317428f, 0.00303526991f, 0.00334653561f, 0.00367650716f, 0.00402471703f, 0.00439144205f, 0.00477695325f,
	0.00518151652f, 0.00560539123f, 0.00604883302f, 0.00651209056f, 0.00699541019f, 0.00749903172f, 0.00802319311f, 0.00856812578f,
	0.00913405884f, 0.00972121675f, 0.010329823f, 0.0109600937f, 0.0116122449f, 0.012286488f, 0.0129830325f, 0.0137020824f,
	0.0144438436f, 0.0152085144f, 0.0159962922f, 0.0168073755f, 0.0176419541f, 0.01850022f, 0.0193823613f, 0.0202885624f,
	0.0212190095f, 0.0221738853f, 0.0231533665f, 0.0241576321f, 0.0251868591f, 0.0262412224f, 0.0273208916f, 0.02842604f,
	0.0295568332f, 0.0307134427f, 0.0318960324f, 0.0331047662f, 0.0343398079f, 0.0356013142f, 0.0368894488f, 0.0382043719f,
	0.0395462364f, 0.0409151949f, 0.0423114114f, 0.0437350273f, 0.045186203f, 0.0466650873f, 0.048171822f, 0.0497065671f,
	0.0512694567f, 0.0528606474f, 0.054480277f, 0.0561284907f, 0.0578054301f, 0.0595112368f, 0.0612460524f, 0.0630100146f,
	0.064803265f, 0.0666259378f, 0.0684781671f, 0.0703600943f, 0.0722718462f, 0.0742135644f, 0.0761853829f, 0.078187421f,
	0.0802198201f, 0.0822827071f, 0.0843762085f, 0.0865004584f, 0.0886555836f, 0.0908417106f, 0.0930589586f, 0.0953074694f,
	0.097587347f, 0.0998987257f, 0.102241732f, 0.104616486f, 0.107023105f, 0.10946171f, 0.111932427f, 0.114435375f,
	0.116970666f, 0.119538426f, 0.122138768f, 0.124771819f, 0.127437681f, 0.130136475f, 0.13286832f, 0.135633335f,
	0.138431609f, 0.141263291f, 0.144128472f, 0.147027269f, 0.149959788f, 0.152926147f, 0.155926466f, 0.158960834f,
	0.162029371f, 0.165132195f, 0.168269396f, 0.171441093f, 0.174647406f, 0.177888408f, 0.18116425f, 0.18447499f,
	0.187820777f, 0.191201687f, 0.194617823f, 0.198069319f, 0.20155625f, 0.205078736f, 0.208636865f, 0.212230757f,
	0.215860501f, 0.219526201f, 0.223227963f, 0.226965874f, 0.230740041f, 0.23455058f, 0.238397568f, 0.242281124f,
	0.246201321f, 0.25015828f, 0.254152089f, 0.258182853f, 0.262250662f, 0.266355604f, 0.270497799f, 0.274677306f,
	0.278894275f, 0.283148736f, 0.287440836f, 0.291770637f, 0.296138257f, 0.300543785f, 0.304987311f, 0.309468925f,
	0.313988715f, 0.318546772f, 0.323143214f, 0.327778101f, 0.332451522f, 0.337163627f, 0.341914415f, 0.346704066f,
	0.351532608f, 0.356400132f, 0.361306787f, 0.366252601f, 0.371237665f, 0.376262128f, 0.38132602f, 0.386429429f,
	0.391572475f, 0.396755219f, 0.401977777f, 0.407240212f, 0.412542611f, 0.417885065f, 0.423267663f, 0.428690493f,
	0.434153646f, 0.439657182f, 0.445201188f, 0.450785786f, 0.456411034f, 0.462076992f, 0.467783809f, 0.473531485f,
	0.479320168f, 0.48514995f, 0.491020858f, 0.496932983f, 0.502886474f, 0.50888133f, 0.514917672f, 0.520995557f,
	0.527115107f, 0.533276379f, 0.539479494f, 0.545724452f, 0.552011371f, 0.558340371f, 0.564711511f, 0.571124852f,
	0.577580452f, 0.584078431f, 0.590618849f, 0.597201765f, 0.603827357f, 0.610495567f, 0.617206573f, 0.623960376f,
	0.630757153f, 0.637596846f, 0.644479692f, 0.651405632f, 0.658374786f, 0.665387273f, 0.672443151f, 0.679542482f,
	0.686685324f, 0.693871737f, 0.701101899f, 0.708375752f, 0.715693474f, 0.723055124f, 0.730460763f, 0.73791039f,
	0.745404184f, 0.752942204f, 0.760524511f, 0.768151164f, 0.775822222f, 0.783537805f, 0.791297913f, 0.799102724f,
	0.806952238f, 0.814846575f, 0.822785735f, 0.830769897f, 0.838799f, 0.846873224f, 0.854992628f, 0.863157213f,
	0.871367097f, 0.8796224f, 0.887923121f, 0.896269321f, 0.904661179f, 0.913098633f, 0.921581864f, 0.930110872f,
	0.938685715f, 0.947306514f, 0.955973327f, 0.964686215f, 0.973445296f, 0.982250571f, 0.991102099f, 1.0f,
};
