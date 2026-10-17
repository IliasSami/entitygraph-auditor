import { NextResponse } from "next/server";
import { PrismGeoService } from "@/lib/prism-geo/db";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const brandId = searchParams.get("brandId") || undefined;

    const availableBrands = PrismGeoService.getBrands();
    const data = PrismGeoService.computeBrandVisibility(brandId);

    if (!data) {
      return NextResponse.json(
        {
          error: "No brand records found in PrismGEO database",
          availableBrands,
        },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      availableBrands,
      data,
    });
  } catch (error: unknown) {
    console.error("API /api/visibility error:", error);
    const message = error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json(
      { error: message },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    // Local-first: no live crawl is performed. This endpoint only acknowledges
    // the request; the caller re-reads the local PrismGEO dataset via GET.
    return NextResponse.json({
      success: true,
      message:
        "No live crawl executed — local-first mode. Re-read the dataset with GET /api/visibility.",
      received: body,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to trigger crawl";
    return NextResponse.json(
      { error: message },
      { status: 500 }
    );
  }
}
